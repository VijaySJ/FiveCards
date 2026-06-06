import logging
from telegram.ext import ContextTypes

from app.services import state_manager
from app.core import game_engine
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import send_dm, get_group_link, send_new_turn_message
from app.core.exceptions import GameException
from app.core.card_utils import format_card

logger = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 60

async def start_turn_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, game: dict, message_id: int = None, is_startgame: bool = False) -> None:
    """Schedule a job to auto-drop a card if the player doesn't act in time.

    FIX #7: If the next player has 0 cards (pending_auto_declare is set),
    immediately trigger process_declare for them instead of starting a timer.
    """
    if not context.job_queue:
        logger.warning("JobQueue not available, timer skipped.")
        return

    # FIX #7: Handle 0-card player — auto-declare immediately
    turn_idx = game["current_turn_idx"]
    current_player = game["players"][turn_idx]
    current_user_id = current_player["user_id"]

    if game.get("pending_auto_declare") == current_user_id:
        game.pop("pending_auto_declare")
        from app.services import state_manager
        from app.core import game_engine
        from app.services import message_formatter as fmt
        from app.bot import keyboards

        logger.info("Auto-declaring for 0-card player %s in chat %d", current_player["username"], chat_id)
        try:
            round_scores = game_engine.process_declare(game, current_user_id)
            state_manager.update_game(chat_id, game)

            await context.bot.send_message(
                chat_id=chat_id,
                text=fmt.fmt_declaration(current_player["username"]),
                parse_mode="HTML"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=fmt.fmt_all_hands_revealed(game),
                parse_mode="HTML"
            )
            is_last = game_engine.is_game_over(game)
            result_msg = fmt.fmt_round_result(game, round_scores, current_player["username"])
            await context.bot.send_message(
                chat_id=chat_id,
                text=result_msg,
                reply_markup=keyboards.next_round_keyboard(is_last),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Error in pending_auto_declare for %s: %s", current_player["username"], e)
        return

    await cancel_turn_timer(context, chat_id)

    round_num = game["round_current"]
    player_id = game["players"][turn_idx]["user_id"]
    job_name = f"timer_{chat_id}"

    context.job_queue.run_once(
        auto_drop_callback,
        TURN_TIMEOUT_SECONDS,
        chat_id=chat_id,
        name=job_name,
        data={
            "turn_idx": turn_idx,
            "round_num": round_num,
            "player_id": player_id,
        }
    )

    # Schedule live countdown updates at 15s, 30s, and 45s intervals
    for elapsed, remaining in [(15, 45), (30, 30), (45, 15)]:
        context.job_queue.run_once(
            update_timer_callback,
            elapsed,
            chat_id=chat_id,
            name=job_name,
            data={
                "turn_idx": turn_idx,
                "round_num": round_num,
                "player_id": player_id,
                "time_left": remaining,
            }
        )


async def cancel_turn_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Cancel any existing timer for the chat."""
    if not context.job_queue:
        return
    job_name = f"timer_{chat_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()

async def pin_turn_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pins the turn announcement message to the group chat."""
    job = context.job
    chat_id = job.chat_id
    message_id = job.data["message_id"]
    
    try:
        game = state_manager.get_game_or_raise(chat_id)
        prev_pinned = game.get("pinned_message_id")
        
        if prev_pinned:
            try:
                await context.bot.unpin_chat_message(chat_id=chat_id, message_id=prev_pinned)
            except Exception:
                pass
                
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            disable_notification=True
        )
        game["pinned_message_id"] = message_id
        state_manager.update_game(chat_id, game)
    except GameException:
        pass
    except Exception as e:
        logger.warning("Could not pin turn message: %s", e)


async def update_timer_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executed every 15 seconds to update the persistent keyboard message."""
    job = context.job
    chat_id = job.chat_id
    data = job.data

    try:
        game = state_manager.get_game_or_raise(chat_id)

        # Verify the turn hasn't changed
        if game["round_current"] != data["round_num"] or game["current_turn_idx"] != data["turn_idx"]:
            return

        # CHANGE #1: use keyboard_message_id from game state (single persistent message)
        message_id = game.get("keyboard_message_id") or data.get("message_id")
        time_left = data["time_left"]

        if message_id:
            try:
                bot_info = await context.bot.get_me()
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=fmt.fmt_turn_announcement(game, time_left),
                    reply_markup=keyboards.persistent_game_keyboard(bot_info.username),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.debug("Timer update edit failed (ok if message unchanged): %s", e)
    except GameException:
        pass  # Game ended or deleted
    except Exception as e:
        logger.error("Error in update_timer_callback: %s", e)

async def auto_drop_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Executed when a player's turn times out."""
    job = context.job
    chat_id = job.chat_id
    data = job.data

    try:
        game = state_manager.get_game_or_raise(chat_id)

        # Verify the turn hasn't changed
        if game["round_current"] != data["round_num"] or game["current_turn_idx"] != data["turn_idx"]:
            return

        player_id = data["player_id"]
        player = state_manager.get_player(game, player_id)
        if not player:
            return

        username = player["username"]
        drawn_card, dropped_cards, hand_empty = game_engine.process_timeout(game, player_id)
        state_manager.update_game(chat_id, game)

        # Announce timeout to group
        if dropped_cards:
            formatted_drops = [format_card(c) for c in dropped_cards]
            announcement = (
                f"⏰ <b>Time's up!</b>\n"
                f"👤 {username} took too long and randomly dropped: {', '.join(formatted_drops)}"
            )
            if drawn_card:
                announcement += f"\n🎴 And automatically drew from the pile."
        elif drawn_card:
            announcement = f"⏰ <b>Time's up!</b>\n👤 {username} took too long and automatically drew from the pile."
        else:
            announcement = f"⏰ <b>Time's up!</b>\n👤 {username} had no cards to drop!"
        await context.bot.send_message(
            chat_id=chat_id,
            text=announcement,
            parse_mode="HTML"
        )

        if hand_empty:
            await context.bot.send_message(
                chat_id=chat_id,
                text=fmt.fmt_player_hand_empty(username),
                parse_mode="HTML"
            )

        # Send new turn message first — updates keyboard_message_id
        await send_new_turn_message(context, chat_id, game)

        # Send DM to timed-out player with updated hand
        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        await send_dm(
            context.bot, player_id, hand_msg,
            username=username, chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )

        await start_turn_timer(
            context, chat_id, game,
            message_id=game.get("keyboard_message_id"),
            is_startgame=False,
        )

    except GameException as e:
        logger.error("Error in auto_drop_callback: %s", e.message)
    except Exception as e:
        logger.error("Unexpected error in auto_drop_callback: %s", e)
