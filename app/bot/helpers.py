"""
helpers.py — Shared Telegram bot helpers (DM sending, etc.).
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import Forbidden

from app.services import message_formatter as fmt
from app.services import state_manager
from app.bot import keyboards

logger = logging.getLogger(__name__)








async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Check if a user is the group owner or an administrator.

    Args:
        bot: Telegram Bot instance.
        chat_id: Group chat ID.
        user_id: User ID to check.

    Returns:
        True if the user is the group creator or an administrator.
    """
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("creator", "administrator")
    except Exception as e:
        logger.warning("Failed to check admin status for user %d in chat %d: %s", user_id, chat_id, e)
        return False


async def get_group_link(bot: Bot, chat_id: int, message_id: int = None) -> str:
    """Get the group's URL dynamically from Telegram.

    Returns a link to the GROUP CHAT (not a specific message).

    Linking to a specific message_id caused "Message doesn't exist" errors
    because send_new_turn_message() deletes the old keyboard message every
    turn, but only the acting player's DM gets updated. All other players'
    DMs kept a stale link to the deleted message.

    The message_id parameter is kept for backward-compatibility but ignored.

    Args:
        bot: Telegram Bot instance.
        chat_id: Group chat ID.
        message_id: Ignored — kept so callers don't need to change.

    Returns:
        URL string opening the group chat (no specific message).
    """
    try:
        chat = await bot.get_chat(chat_id)
        if chat.username:
            return f"https://t.me/{chat.username}"
    except Exception as e:
        logger.debug("Safe check failed for chat %d: %s", chat_id, e)

    # Fallback for private groups — strip the -100 supergroup prefix
    clean_id = str(chat_id)
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]
        
    # Private group links MUST have a message ID to be valid. 
    # 999999999 is used to jump to the bottom of the chat without pointing to a deleted message.
    # We intentionally ignore the passed in message_id because pointing to a deleted message 
    # (like old turn announcements) causes a "Message doesn't exist" error toast.
    msg_id = 999999999
    return f"https://t.me/c/{clean_id}/{msg_id}"

async def send_new_turn_message(
    context,
    chat_id: int,
    game: dict,
    time_left: int = 60,
    edit_only: bool = False,
) -> None:
    """Send a new turn announcement message, or edit existing if edit_only=True."""
    try:
        bot_info = await context.bot.get_me()
        text = fmt.fmt_turn_announcement(game, time_left)
        markup = keyboards.persistent_game_keyboard(bot_info.username, game=game)
        msg_id = game.get("keyboard_message_id")
        
        if edit_only and msg_id:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode="HTML"
                )
                return
            except Exception:
                pass # Fallback to send new
                
        # Delete old message to prevent chat clutter if not editing
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception:
                pass
                
        # Send a brand new message at the bottom of the chat
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
        game["keyboard_message_id"] = msg.message_id
        state_manager.update_game(chat_id, game)
    except Exception as e:
        logger.error("Could not update turn message: %s", e, exc_info=True)
        raise e


async def check_and_handle_end_of_round(context, chat_id: int, game: dict, user_id: int, username: str) -> bool:
    """Check if only 1 active player is left, and if so, end the round."""
    from app.core import game_engine
    from app.bot.timer import cancel_turn_timer
    
    active_players_count = sum(1 for p in game["players"] if len(p["hand"]) > 0)
    if active_players_count <= 1:
        round_scores = game_engine.process_declare(game, user_id, is_auto=True)
        state_manager.update_game(chat_id, game)
        await cancel_turn_timer(context, chat_id)
        
        await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_declaration(username + " (Auto)"), parse_mode="HTML")
        await context.bot.send_message(chat_id=chat_id, text=fmt.fmt_all_hands_revealed(game), parse_mode="HTML")
        
        result_msg = fmt.fmt_round_result(game, round_scores, username)
        is_last = game_engine.is_game_over(game)
        await context.bot.send_message(
            chat_id=chat_id, 
            text=result_msg, 
            reply_markup=keyboards.next_round_keyboard(is_last), 
            parse_mode="HTML"
        )
        return True
    return False
