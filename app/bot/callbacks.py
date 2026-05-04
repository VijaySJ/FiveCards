"""
callbacks.py — CallbackQueryHandler dispatcher for the 5 Cards bot.

Handles all inline keyboard button presses and routes them
to the appropriate game logic.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.core import game_engine
from app.services import state_manager
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import send_dm, is_group_admin, get_group_link
from app.bot.timer import start_turn_timer, cancel_turn_timer
from app.core.exceptions import GameException

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline keyboard button presses.

    Dispatches based on callback_data prefix:
      - "view_hand" → DM player their hand
      - "action:pick" → pick open card
      - "action:draw" → draw from pile
      - "action:declare" → declare
      - "action:drop_prompt" → prompt player to type /drop
      - "see_scores" → show scores
      - "next_round" → start next round
      - "finish_game" → end game and show leaderboard
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        if data == "view_hand":
            game = state_manager.get_game_or_raise(chat_id)
            player = state_manager.get_player_or_raise(game, user.id)
            hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
            group_link = await get_group_link(context.bot, chat_id)
            await send_dm(
                context.bot, user.id, hand_msg,
                username=player["username"], chat_id=chat_id,
                reply_markup=keyboards.dm_keyboard(group_link),
            )

        elif data == "action:pick":
            game = state_manager.get_game_or_raise(chat_id)
            picked_card = game_engine.process_pick(game, user.id)
            state_manager.update_game(chat_id, game)

            player = state_manager.get_player(game, user.id)
            username = player["username"] if player else "Unknown"

            await context.bot.send_message(
                chat_id=chat_id,
                text=fmt.fmt_player_picked(username),
                reply_markup=keyboards.turn_keyboard(game),
            )

            # Send hand via DM with navigation
            discard_msg = fmt.fmt_must_discard_dm(player, picked_card, game["joker_rank"])
            group_link = await get_group_link(context.bot, chat_id)
            await send_dm(
                context.bot, user.id, discard_msg,
                username=username, chat_id=chat_id,
                reply_markup=keyboards.dm_keyboard(group_link),
            )

        elif data == "action:draw":
            game = state_manager.get_game_or_raise(chat_id)
            if not game["deck"]:
                await context.bot.send_message(
                    chat_id=chat_id, text=fmt.fmt_reshuffle_notice(),
                )
            drawn_card = game_engine.process_draw(game, user.id)
            state_manager.update_game(chat_id, game)

            player = state_manager.get_player(game, user.id)
            username = player["username"] if player else "Unknown"

            await context.bot.send_message(
                chat_id=chat_id,
                text=fmt.fmt_player_drew(username),
                reply_markup=keyboards.turn_keyboard(game),
            )

            # Send hand via DM with navigation
            discard_msg = fmt.fmt_must_discard_dm(player, drawn_card, game["joker_rank"])
            group_link = await get_group_link(context.bot, chat_id)
            await send_dm(
                context.bot, user.id, discard_msg,
                username=username, chat_id=chat_id,
                reply_markup=keyboards.dm_keyboard(group_link),
            )

        elif data == "action:declare":
            game = state_manager.get_game_or_raise(chat_id)
            declarer = state_manager.get_player(game, user.id)
            declarer_name = declarer["username"] if declarer else "Unknown"

            round_scores = game_engine.process_declare(game, user.id)
            state_manager.update_game(chat_id, game)

            await context.bot.send_message(
                chat_id=chat_id, text=fmt.fmt_declaration(declarer_name),
            )
            await context.bot.send_message(
                chat_id=chat_id, text=fmt.fmt_all_hands_revealed(game),
            )

            is_last = game_engine.is_game_over(game)
            result_msg = fmt.fmt_round_result(game, round_scores, declarer_name)
            await context.bot.send_message(
                chat_id=chat_id, text=result_msg,
                reply_markup=keyboards.next_round_keyboard(is_last),
            )



        elif data == "see_scores":
            game = state_manager.get_game_or_raise(chat_id)
            scores_msg = fmt.fmt_scores(game)
            await context.bot.send_message(chat_id=chat_id, text=scores_msg)

        elif data == "next_round":
            game = state_manager.get_game_or_raise(chat_id)
            is_admin = await is_group_admin(context.bot, chat_id, user.id)
            if game["admin_id"] != user.id and not is_admin:
                await query.answer("🔒 Only the game creator or group admins can start the next round.", show_alert=True)
                return
            if game_engine.is_game_over(game):
                await query.answer("🏁 All rounds completed!", show_alert=True)
                return

            game_engine.start_next_round(game)
            state_manager.update_game(chat_id, game)

            group_link = await get_group_link(context.bot, chat_id)
            for player in game["players"]:
                uid = player["user_id"]
                hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
                await send_dm(
                    context.bot, uid, hand_msg,
                    username=player["username"], chat_id=chat_id,
                    reply_markup=keyboards.dm_keyboard(group_link),
                )

            start_msg = fmt.fmt_game_starting(game)
            await context.bot.send_message(
                chat_id=chat_id, text=start_msg,
                reply_markup=keyboards.turn_keyboard(game),
            )
            
            start_turn_timer(context, chat_id, game)

        elif data == "finish_game":
            game = state_manager.get_game_or_raise(chat_id)
            is_admin = await is_group_admin(context.bot, chat_id, user.id)
            if game["admin_id"] != user.id and not is_admin:
                await query.answer("🔒 Only the game creator or group admins can finish the game.", show_alert=True)
                return

            leaderboard = game_engine.end_game(game)
            state_manager.delete_game(chat_id)
            cancel_turn_timer(context, chat_id)
            await context.bot.send_message(chat_id=chat_id, text=leaderboard)

        else:
            logger.warning("Unknown callback data: %s", data)

    except GameException as e:
        await query.answer(e.message, show_alert=True)
