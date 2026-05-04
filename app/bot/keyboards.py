"""
keyboards.py — InlineKeyboardMarkup builders for the 5 Cards game bot.

All functions return telegram InlineKeyboardMarkup objects ready to be
attached to bot messages.

Keyboards are split by turn phase:
  - turn_keyboard()    → choose_action phase (Pick / Draw / Declare)
  - discard_keyboard() → must_discard phase  (Drop the Card)
Both include navigation buttons for group ↔ DM switching.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config.settings import BOT_USERNAME, GROUP_LINK


def turn_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard for the 'choose_action' phase.

    Shown at the start of each turn. Only the active player's
    button presses will be accepted by the callback handler.

    Buttons:
      Row 1: [🃏 Pick Open Card]  [🎴 Draw from Pile]
      Row 2: [🏳️ Declare]
      Row 3: [🃏 Card In Hand →]

    Returns:
        InlineKeyboardMarkup with turn action buttons.
    """
    bot_dm_link = f"https://t.me/{BOT_USERNAME}"
    keyboard = [
        [
            InlineKeyboardButton("🃏 Pick Open Card", callback_data="action:pick"),
            InlineKeyboardButton("🎴 Draw from Pile", callback_data="action:draw"),
        ],
        [
            InlineKeyboardButton("🏳️ Declare", callback_data="action:declare"),
        ],
        [
            InlineKeyboardButton("🃏 Card In Hand →", url=bot_dm_link),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def discard_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard for the 'must_discard' phase.

    Shown after a player picks or draws a card.

    Buttons:
      Row 1: [⏬ Drop the Card]
      Row 2: [🃏 Card In Hand →]

    Returns:
        InlineKeyboardMarkup with the drop prompt button.
    """
    bot_dm_link = f"https://t.me/{BOT_USERNAME}"
    keyboard = [
        [
            InlineKeyboardButton("⏬ Drop the Card", callback_data="action:drop_prompt"),
        ],
        [
            InlineKeyboardButton("🃏 Card In Hand →", url=bot_dm_link),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def dm_keyboard() -> InlineKeyboardMarkup:
    """Build the keyboard shown in bot DM messages.

    Provides a quick link back to the group chat.

    Buttons:
      [🔙 Go Back to Play Area]

    Returns:
        InlineKeyboardMarkup with a group-link button.
    """
    keyboard = [
        [InlineKeyboardButton("🔙 Go Back to Play Area", url=GROUP_LINK)],
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
