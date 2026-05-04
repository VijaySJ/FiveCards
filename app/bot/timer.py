import logging
from telegram.ext import ContextTypes

from app.services import state_manager
from app.core import game_engine
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import send_dm, get_group_link
from app.core.exceptions import GameException

logger = logging.getLogger(__name__)

TURN_TIMEOUT_SECONDS = 60

def start_turn_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int, game: dict, message_id: int = None, is_startgame: bool = False) -> None:
    """Schedule a job to auto-drop a card if the player doesn't act in time."""
    if not context.job_queue:
        logger.warning("JobQueue not available, timer skipped.")
        return

    cancel_turn_timer(context, chat_id)
    
    # Store current turn info to ensure we don't drop if turn has advanced naturally
    turn_idx = game["current_turn_idx"]
    round_num = game["round_current"]
    player_id = game["players"][turn_idx]["user_id"]
    
    job_name = f"timer_{chat_id}"
    
    # Schedule updates at 15s, 30s, 45s if we have a message to edit
    if message_id:
        for elapsed in (15, 30, 45):
            time_left = TURN_TIMEOUT_SECONDS - elapsed
            context.job_queue.run_once(
                update_timer_callback,
                elapsed,
                chat_id=chat_id,
                name=job_name,
                data={
                    "turn_idx": turn_idx,
                    "round_num": round_num,
                    "time_left": time_left,
                    "message_id": message_id,
                    "is_startgame": is_startgame,
                }
            )
        
        # Schedule the pin job immediately
        context.job_queue.run_once(
            pin_turn_job,
            0,
            chat_id=chat_id,
            data={"message_id": message_id}
        )

    context.job_queue.run_once(
        auto_drop_callback,
        TURN_TIMEOUT_SECONDS,
        chat_id=chat_id,
        name=job_name,
        data={
            "turn_idx": turn_idx,
            "round_num": round_num,
            "player_id": player_id
        }
    )

def cancel_turn_timer(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
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
    """Executed every 15 seconds to update the turn announcement message."""
    job = context.job
    chat_id = job.chat_id
    data = job.data
    
    try:
        game = state_manager.get_game_or_raise(chat_id)
        
        # Verify the turn hasn't changed
        if game["round_current"] != data["round_num"] or game["current_turn_idx"] != data["turn_idx"]:
            return
            
        message_id = data["message_id"]
        time_left = data["time_left"]
        is_startgame = data["is_startgame"]
        
        if is_startgame:
            new_text = fmt.fmt_game_starting(game, time_left)
        else:
            new_text = fmt.fmt_turn_announcement(game, time_left)
            
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            reply_markup=keyboards.turn_keyboard(game)
        )
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
        
        # Announce to group
        announcement = f"⏰ <b>Time's up!</b>\n{username} took too long and randomly dropped: {', '.join(dropped_cards)}"
        await context.bot.send_message(
            chat_id=chat_id,
            text=announcement,
            parse_mode="HTML"
        )
        
        if hand_empty:
            await context.bot.send_message(
                chat_id=chat_id, 
                text=fmt.fmt_player_hand_empty(username)
            )

        # Update DM for the timed-out player
        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        await send_dm(
            context.bot, player_id, hand_msg,
            username=username, chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )

        # Start next turn automatically
        turn_msg = fmt.fmt_turn_announcement(game, 60)
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=turn_msg,
            reply_markup=keyboards.turn_keyboard(game)
        )
        start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=False)
            
    except GameException as e:
        logger.error("Error in auto_drop_callback: %s", e.message)
    except Exception as e:
        logger.error("Unexpected error in auto_drop_callback: %s", e)
