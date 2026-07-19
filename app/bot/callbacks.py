"""
callbacks.py — CallbackQueryHandler dispatcher for the 5 Cards bot.

Handles all inline keyboard button presses and routes them
to the appropriate game logic.

PERSISTENT KEYBOARD (CHANGE #1):
  The keyboard is sent ONCE at game start (stored in game["keyboard_message_id"]).
  On every turn change it is EDITED — never re-sent as a new message.

PHASE GUARDS (CHANGE #2):
  All button presses validate turn ownership and current phase via
  query.answer() toast alerts (show_alert=False) so no chat message is sent.
"""

import logging
import asyncio

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.core import game_engine
from app.services import state_manager
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import is_group_admin, get_group_link, send_new_turn_message
from app.bot.timer import start_turn_timer, cancel_turn_timer
from app.core.exceptions import GameException

logger = logging.getLogger(__name__)





async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all inline keyboard button presses.

    Dispatches based on callback_data:
      - "view_hand"      → DM player their hand (legacy)
      - "action:hand"    → DM player hand with deep-link back to game
      - "action:pick"    → pick open card
      - "action:draw"    → draw from pile
      - "action:declare" → declare (must_discard phase only)
      - "see_scores"     → show scores
      - "next_round"     → start next round
      - "finish_game"    → end game and show leaderboard
    """
    query = update.callback_query

    data = query.data
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        # ── Action buttons that require an active game + turn checks ──────────
        if data in ("action:pick", "action:draw", "action:declare", "action:hand", "confirm:declare", "cancel:declare"):
            game = state_manager.get_game_or_raise(chat_id)
            current_player_id = game["players"][game["current_turn_idx"]]["user_id"]
            phase = game["turn_phase"]

            # CHANGE #2 Guard 1: Only the current player can act
            if data != "action:hand" and user.id != current_player_id:
                await query.answer("⛔ It's not your turn!", show_alert=False)
                return

            # CHANGE #2 Guard 2: Phase-specific restrictions
            if data == "action:pick" and phase != "must_draw":
                await query.answer("⛔ You must drop a card first!", show_alert=False)
                return

            if data == "action:draw" and phase != "must_draw":
                await query.answer("⛔ You must drop a card first!", show_alert=False)
                return

            if data in ("action:declare", "confirm:declare") and phase != "must_discard":
                await query.answer(
                    "⛔ You can only declare at the start of your turn!",
                    show_alert=False,
                )
                return

            # ── action:pick ───────────────────────────────────────────────────
            if data == "action:pick":
                picked_card = game_engine.process_pick(game, user.id)
                
                warning_msg_id = game.pop("warning_message_id", None)
                if warning_msg_id:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=warning_msg_id)
                    except Exception:
                        pass
                        
                state_manager.update_game(chat_id, game)

                # Step 1: Send a NEW turn message for individual turn logs
                await send_new_turn_message(context, chat_id, game)


                
                # Step 2: Start 60s timer for next player
                await start_turn_timer(context, chat_id, game)

            # ── action:draw ───────────────────────────────────────────────────
            elif data == "action:draw":
                if not game["deck"]:
                    await context.bot.send_message(
                        chat_id=chat_id, text=fmt.fmt_reshuffle_notice(),
                    )
                drawn_card = game_engine.process_draw(game, user.id)
                
                warning_msg_id = game.pop("warning_message_id", None)
                if warning_msg_id:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=warning_msg_id)
                    except Exception:
                        pass
                        
                state_manager.update_game(chat_id, game)

                # Step 1: Send a NEW turn message for individual turn logs
                await send_new_turn_message(context, chat_id, game)


                
                # Step 2: Start 60s timer for next player
                await start_turn_timer(context, chat_id, game)


            elif data == "action:declare":
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=game.get("keyboard_message_id"),
                        reply_markup=keyboards.declare_confirm_keyboard()
                    )
                except Exception as e:
                    logger.warning("Failed to show declare confirm keyboard: %s", e)
                return

            elif data == "cancel:declare":
                bot_info = await context.bot.get_me()
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=game.get("keyboard_message_id"),
                        reply_markup=keyboards.persistent_game_keyboard(bot_info.username, game=game)
                    )
                except Exception as e:
                    logger.warning("Failed to restore persistent keyboard: %s", e)
                return

            elif data == "confirm:declare":
                declarer = state_manager.get_player(game, user.id)
                declarer_name = declarer["username"] if declarer else "Unknown"

                await cancel_turn_timer(context, chat_id)

                round_scores = game_engine.process_declare(game, user.id)
                state_manager.update_game(chat_id, game)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=fmt.fmt_declaration(declarer_name),
                    parse_mode="HTML"
                )
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=fmt.fmt_all_hands_revealed(game),
                    parse_mode="HTML"
                )

                result_msg = fmt.fmt_round_result(game, round_scores, declarer_name)
                is_last = game_engine.is_game_over(game)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=result_msg,
                    reply_markup=keyboards.next_round_keyboard(is_last),
                    parse_mode="HTML"
                )



        # ── action:join ───────────────────────────────────────────────────────
        elif data == "action:join":
            game = state_manager.get_game_or_raise(chat_id)
            username = user.first_name or user.username or f"Player_{user.id}"
            
            if any(p["user_id"] == user.id for p in game["players"]):
                await query.answer("✅ You are already in the game!", show_alert=True)
                return
                
            game_engine.add_player(game, user.id, username, tg_username=user.username)
            state_manager.update_game(chat_id, game)

            msg = fmt.fmt_player_joined(username, len(game["players"]))
            await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            await query.answer("🎉 Successfully joined the game!")
            logger.info("Button /join by %s in chat %d", username, chat_id)


        # ── see_scores ────────────────────────────────────────────────────────
        elif data == "see_scores":
            game = state_manager.get_game_or_raise(chat_id)
            scores_msg = fmt.fmt_scores(game)
            await context.bot.send_message(chat_id=chat_id, text=scores_msg, parse_mode="HTML")

        # ── next_round ────────────────────────────────────────────────────────
        elif data == "next_round":
            game = state_manager.get_game_or_raise(chat_id)
            is_admin = await is_group_admin(context.bot, chat_id, user.id)
            if game["admin_id"] != user.id and not is_admin:
                await query.answer(
                    "🔒 Only the game creator or group admins can start the next round.",
                    show_alert=True,
                )
                return
            if game_engine.is_game_over(game):
                await query.answer("🏁 All rounds completed!", show_alert=True)
                return

            game_engine.start_next_round(game)
            state_manager.update_game(chat_id, game)

            # Send a NEW turn message for the new round
            await send_new_turn_message(context, chat_id, game)

            await start_turn_timer(
                context, chat_id, game,
                message_id=game.get("keyboard_message_id"),
                is_startgame=False,
            )

        # ── finish_game ───────────────────────────────────────────────────────
        elif data == "finish_game":
            game = state_manager.get_game_or_raise(chat_id)
            is_admin = await is_group_admin(context.bot, chat_id, user.id)
            if game["admin_id"] != user.id and not is_admin:
                await query.answer(
                    "🔒 Only the game creator or group admins can finish the game.",
                    show_alert=True,
                )
                return

            leaderboard = game_engine.end_game(game)
            state_manager.delete_game(chat_id)
            await cancel_turn_timer(context, chat_id)
            await context.bot.send_message(chat_id=chat_id, text=leaderboard, parse_mode="HTML")

        else:
            logger.warning("Unknown callback data: %s", data)

    except GameException as e:
        await query.answer(e.message, show_alert=True)
    finally:
        try:
            await query.answer()
        except Exception:
            pass
