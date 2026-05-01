"""
keyboards.py — InlineKeyboardMarkup builders for the 5 Cards game bot.

All functions return telegram InlineKeyboardMarkup objects ready to be
attached to bot messages.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


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


def turn_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard shown at the start of each turn.

    Only the active player's button presses will be accepted.

    Buttons:
      Row 1: [🃏 Pick Open Card]  [🎴 Draw from Pile]
      Row 2: [🏳️ Declare]

    Returns:
        InlineKeyboardMarkup with turn action buttons.
    """
    keyboard = [
        [
            InlineKeyboardButton("🃏 Pick Open Card", callback_data="action:pick"),
            InlineKeyboardButton("🎴 Draw from Pile", callback_data="action:draw"),
        ],
        [
            InlineKeyboardButton("🏳️ Declare", callback_data="action:declare"),
        ],
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


def drop_reminder_keyboard() -> InlineKeyboardMarkup:
    """Build a small helper keyboard shown when player must discard.

    Provides a reminder — actual drop is done via /drop command.

    Buttons:
      [📋 View My Hand]

    Returns:
        InlineKeyboardMarkup with a hand-view button.
    """
    keyboard = [
        [InlineKeyboardButton("📋 View My Hand", callback_data="view_hand")],
    ]
    return InlineKeyboardMarkup(keyboard)
