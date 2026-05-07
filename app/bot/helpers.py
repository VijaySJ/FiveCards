"""
helpers.py — Shared Telegram bot helpers (DM sending, etc.).
"""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import Forbidden

from app.services import message_formatter as fmt

logger = logging.getLogger(__name__)


async def send_dm(
    bot: Bot,
    user_id: int,
    text: str,
    username: str = "",
    chat_id: int = 0,
    reply_markup=None,
) -> bool:
    """Attempt to send a DM to a user. If blocked/not started, notify group.

    Args:
        bot: Telegram Bot instance.
        user_id: Target user's Telegram ID.
        text: Message text to send.
        username: Player's display name (for error messages).
        chat_id: Group chat ID (for sending error messages).
        reply_markup: Optional InlineKeyboardMarkup to attach.

    Returns:
        True if DM was sent successfully, False otherwise.
    """
    try:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
        return True
    except Forbidden:
        bot_me = await bot.get_me()
        if chat_id:
            warning = fmt.fmt_dm_warning(username, bot_me.username or "the_bot")
            await bot.send_message(chat_id=chat_id, text=warning)
        logger.warning("Cannot DM user %s (%d) — privacy/block", username, user_id)
        return False
    except Exception as e:
        logger.error("Failed to DM user %d: %s", user_id, e)
        return False


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


async def get_group_link(bot: Bot, chat_id: int, message_id: int = 1) -> str:
    """Get the group's URL dynamically from Telegram.

    Tries in order:
      1. Public username → t.me/<username>
      2. Existing invite link from chat info
      3. Fallback: t.me/c/<chat_id> deep link

    Args:
        bot: Telegram Bot instance.
        chat_id: Group chat ID.

    Returns:
        URL string for the group chat.
    """
    try:
        chat = await bot.get_chat(chat_id)
        # Public group with username
        if chat.username:
            return f"https://t.me/{chat.username}"
        # Private group with existing invite link
        if chat.invite_link:
            return chat.invite_link
    except Exception as e:
        logger.warning("Failed to get chat info for %d: %s", chat_id, e)

    # Fallback: Telegram deep link format for private groups
    # Remove the -100 prefix that Telegram adds to supergroup IDs
    clean_id = str(chat_id)
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]
    return f"https://t.me/c/{clean_id}/{message_id}"

async def send_new_turn_message(
    context,
    chat_id: int,
    game: dict,
    time_left: int = 60,
) -> None:
    """Send a NEW turn announcement message instead of editing the old one.
    
    This fulfills the user request for 'individual messages' per turn.
    """
    from app.services import state_manager
    from app.services import message_formatter as fmt
    from app.bot import keyboards
    
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=fmt.fmt_turn_announcement(game, time_left),
            reply_markup=keyboards.persistent_game_keyboard(),
        )
        # Update state with the new message ID so timers can still edit THIS message
        game["keyboard_message_id"] = msg.message_id
        state_manager.update_game(chat_id, game)
    except Exception as e:
        logger.warning("Could not send new turn message: %s", e)
