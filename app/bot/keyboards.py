"""
keyboards.py — InlineKeyboardMarkup builders for the 5 Cards game bot.

All functions return telegram InlineKeyboardMarkup objects ready to be
attached to bot messages.

All action buttons are shown in a single turn_keyboard() layout.
The game engine handles phase validation and returns appropriate errors
if a button is pressed out of sequence.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config.settings import BOT_USERNAME


def turn_keyboard(game: dict = None) -> InlineKeyboardMarkup:
    """Build the main turn keyboard with all action buttons.

    If game is in 'must_discard' phase, only the Drop button is shown.

    Returns:
        InlineKeyboardMarkup with relevant turn action buttons.
    """
    bot_dm_link = f"https://t.me/{BOT_USERNAME}"
    
    if game and game.get("turn_phase") == "must_discard":
        keyboard = [
            [
                InlineKeyboardButton("⏬ Drop the Card", switch_inline_query_current_chat="/drop "),
            ],
            [
                InlineKeyboardButton("🃏 Card In Hand →", url=bot_dm_link),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    keyboard = [
        [
            InlineKeyboardButton("🃏 Pick Open Card", callback_data="action:pick"),
            InlineKeyboardButton("🎴 Draw from Pile", callback_data="action:draw"),
        ],
        [
            InlineKeyboardButton("🏳️ Declare", callback_data="action:declare"),
            InlineKeyboardButton("⏬ Drop the Card", switch_inline_query_current_chat="/drop "),
        ],
        [
            InlineKeyboardButton("🃏 Card In Hand →", url=bot_dm_link),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def dm_keyboard(group_link: str) -> InlineKeyboardMarkup:
    """Build the keyboard shown in bot DM messages.

    Provides a quick link back to the group chat where the game
    is being played. The link is dynamically determined.

    Args:
        group_link: URL to the group chat (dynamic, from chat info).

    Buttons:
      [🔙 Go Back to Play Area]

    Returns:
        InlineKeyboardMarkup with a group-link button.
    """
    keyboard = [
        [InlineKeyboardButton("🔙 Go Back to Play Area", url=group_link)],
    ]
    return InlineKeyboardMarkup(keyboard)


def deal_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard shown after dealing cards.

    Buttons:
      [📋 View My Hand]

    Returns:
        InlineKeyboardMarkup with a single 'view hand' button.
    """
    keyboard = [
        [InlineKeyboardButton("📋 View My Hand", callback_data="view_hand")],
    ]
    return InlineKeyboardMarkup(keyboard)


def scores_keyboard() -> InlineKeyboardMarkup:
    """Build a compact scores keyboard.

    Buttons:
      [📊 See Scores]

    Returns:
        InlineKeyboardMarkup with a scores button.
    """
    keyboard = [
        [InlineKeyboardButton("📊 See Scores", callback_data="see_scores")],
    ]
    return InlineKeyboardMarkup(keyboard)


def next_round_keyboard(is_last_round: bool) -> InlineKeyboardMarkup:
    """Build the keyboard shown after a round ends.

    Args:
        is_last_round: True if the just-completed round was the final one.

    Returns:
        InlineKeyboardMarkup with appropriate buttons.
    """
    if is_last_round:
        keyboard = [
            [
                InlineKeyboardButton("📊 See Scores", callback_data="see_scores"),
                InlineKeyboardButton("🏁 Finish Game", callback_data="finish_game"),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("📊 See Scores", callback_data="see_scores"),
                InlineKeyboardButton("🔄 Next Round", callback_data="next_round"),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)
