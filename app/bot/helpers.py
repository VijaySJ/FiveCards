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


async def send_dm(
    bot: Bot,
    user_id: int,
    text: str,
    username: str = "",
    chat_id: int = 0,
    reply_markup=None,
) -> int:
    """Attempt to send a DM to a user. If blocked/not started, notify group.

    Returns:
        Message ID if DM was sent successfully, 0 otherwise.
    """
    try:
        msg = await bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return msg.message_id
    except Forbidden:
        bot_me = await bot.get_me()
        if chat_id:
            warning = fmt.fmt_dm_warning(username, bot_me.username or "the_bot")
            await bot.send_message(chat_id=chat_id, text=warning, parse_mode="HTML")
        logger.warning("Cannot DM user %s (%d) — privacy/block", username, user_id)
        return 0
    except Exception as e:
        logger.error("Failed to DM user %d: %s", user_id, e)
        return 0


async def update_hand_dm(context, chat_id: int, game: dict, user_id: int) -> None:
    """Update the player's existing DM message with their current hand."""
    player = state_manager.get_player(game, user_id)
    if not player: return
    dm_msg_id = player.get("dm_message_id")
    if not dm_msg_id: return
    
    group_link = await get_group_link(context.bot, chat_id, message_id=game.get("keyboard_message_id", 1))
    text = fmt.fmt_hand_dm(player, game["joker_rank"])
    markup = keyboards.dm_keyboard(group_link)
    
    try:
        await context.bot.edit_message_text(
            chat_id=user_id,
            message_id=dm_msg_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        logger.debug("Failed to update DM for %d: %s", user_id, e)


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
    # Ensure message_id is at least 1 and not None
    msg_id = message_id if message_id else 1

    try:
        chat = await bot.get_chat(chat_id)
        # Public group with username
        if chat.username:
            return f"https://t.me/{chat.username}/{msg_id}"
    except Exception as e:
        logger.debug("Safe check failed for chat %d: %s", chat_id, e)

    # Fallback: Telegram deep link format for private groups
    # Remove the -100 prefix that Telegram adds to supergroup IDs
    clean_id = str(chat_id)
    if clean_id.startswith("-100"):
        clean_id = clean_id[4:]
    elif clean_id.startswith("-"):
        clean_id = clean_id[1:]
    return f"https://t.me/c/{clean_id}/{msg_id}"

async def send_new_turn_message(
    context,
    chat_id: int,
    game: dict,
    time_left: int = 60,
) -> None:
    """Update the turn announcement message (edit existing, or send new if missing)."""
    try:
        bot_info = await context.bot.get_me()
        text = fmt.fmt_turn_announcement(game, time_left)
        markup = keyboards.persistent_game_keyboard(bot_info.username)
        msg_id = game.get("keyboard_message_id")
        
        if msg_id:
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
                pass
                
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
