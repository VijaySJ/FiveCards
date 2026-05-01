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
from app.bot.helpers import send_dm
from app.core.exceptions import GameException

logger = logging.getLogger(__name__)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline keyboard button presses.

    Dispatches based on callback_data prefix:
      - "view_hand" → DM player their hand
      - "action:pick" → pick open card
      - "action:draw" → draw from pile
      - "action:declare" → declare
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
            await send_dm(context.bot, user.id, hand_msg, username=player["username"], chat_id=chat_id)

        elif data == "action:pick":
            game = state_manager.get_game_or_raise(chat_id)
            picked_card, group_dropped = game_engine.process_pick(game, user.id)
            state_manager.update_game(chat_id, game)

            player = state_manager.get_player(game, user.id)
            username = player["username"] if player else "Unknown"

            if group_dropped:
                group_msg = fmt.fmt_group_drop(username, group_dropped, len(player["hand"]))
                await context.bot.send_message(chat_id=chat_id, text=group_msg)
                if not player["hand"]:
                    await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_player_hand_empty(username))
                hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
                await send_dm(context.bot, user.id, hand_msg, username=username, chat_id=chat_id)
                turn_msg = fmt.fmt_turn_announcement(game)
                await context.bot.send_message(chat_id=chat_id, text=turn_msg, reply_markup=keyboards.turn_keyboard())
            else:
                await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_player_picked(username))
                discard_msg = fmt.fmt_must_discard_dm(player, picked_card, game["joker_rank"])
                await send_dm(context.bot, user.id, discard_msg, username=username, chat_id=chat_id)

        elif data == "action:draw":
            game = state_manager.get_game_or_raise(chat_id)
            if not game["deck"]:
                await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_reshuffle_notice())
            drawn_card = game_engine.process_draw(game, user.id)
            state_manager.update_game(chat_id, game)

            player = state_manager.get_player(game, user.id)
            username = player["username"] if player else "Unknown"

            await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_player_drew(username))
            discard_msg = fmt.fmt_must_discard_dm(player, drawn_card, game["joker_rank"])
            await send_dm(context.bot, user.id, discard_msg, username=username, chat_id=chat_id)

        elif data == "action:declare":
            game = state_manager.get_game_or_raise(chat_id)
            declarer = state_manager.get_player(game, user.id)
            declarer_name = declarer["username"] if declarer else "Unknown"

            round_scores = game_engine.process_declare(game, user.id)
            state_manager.update_game(chat_id, game)

            await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_declaration(declarer_name))
            await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_all_hands_revealed(game))

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
            if game["admin_id"] != user.id:
                await query.answer("🔒 Only the admin can start the next round.", show_alert=True)
                return
            if game_engine.is_game_over(game):
                await query.answer("🏁 All rounds completed!", show_alert=True)
                return

            game_engine.start_next_round(game)
            state_manager.update_game(chat_id, game)

            for player in game["players"]:
                uid = player["user_id"]
                hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
                await send_dm(context.bot, uid, hand_msg, username=player["username"], chat_id=chat_id)

            start_msg = fmt.fmt_game_starting(game)
            await context.bot.send_message(chat_id=chat_id, text=start_msg, reply_markup=keyboards.turn_keyboard())

        elif data == "finish_game":
            game = state_manager.get_game_or_raise(chat_id)
            if game["admin_id"] != user.id:
                await query.answer("🔒 Only the admin can finish the game.", show_alert=True)
                return

            leaderboard = game_engine.end_game(game)
            state_manager.delete_game(chat_id)
            await context.bot.send_message(chat_id=chat_id, text=leaderboard)

        else:
            logger.warning("Unknown callback data: %s", data)

    except GameException as e:
        await query.answer(e.message, show_alert=True)
