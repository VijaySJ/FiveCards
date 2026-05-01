"""
helpers.py — Shared Telegram bot helpers (DM sending, etc.).
"""

import logging

from telegram import Bot
from telegram.error import Forbidden

from app.services import message_formatter as fmt

logger = logging.getLogger(__name__)


async def send_dm(bot: Bot, user_id: int, text: str, username: str = "", chat_id: int = 0) -> bool:
    """Attempt to send a DM to a user. If blocked/not started, notify group.

    Args:
        bot: Telegram Bot instance.
        user_id: Target user's Telegram ID.
        text: Message text to send.
        username: Player's display name (for error messages).
        chat_id: Group chat ID (for sending error messages).

    Returns:
        True if DM was sent successfully, False otherwise.
    """
    try:
        await bot.send_message(chat_id=user_id, text=text)
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
