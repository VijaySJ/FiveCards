"""
keyboards.py — InlineKeyboardMarkup builders for the 5 Cards game bot.

All functions return telegram InlineKeyboardMarkup objects ready to be
attached to bot messages.

PERSISTENT KEYBOARD:
  persistent_game_keyboard() is sent ONCE when the game starts and is
  EDITED (never re-sent) on every turn change.  All 5 buttons are always
  visible; phase validation is enforced via toast alerts in callbacks.py.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config.settings import BOT_USERNAME


def persistent_game_keyboard(bot_username: str = "fivecardsbot") -> InlineKeyboardMarkup:
    """Build the single persistent game keyboard shown throughout the game.

    This keyboard is sent ONCE at game start and the message is EDITED
    on every turn — it is NEVER re-sent as a new message.

    All 5 buttons are always visible regardless of turn phase.
    Phase guards are enforced in callbacks.py via toast alerts so
    players get instant feedback without a new chat message.

    Layout:
        [📥 Pick Open Card]  [🎴 Draw from Pile]
        [         🏳️ Declare         ]
        [         ⏬ Drop the Card     ]
        [         🃏 Card In Hand →    ]

    Returns:
        InlineKeyboardMarkup with all action buttons.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Pick Open Card", callback_data="action:pick"),
            InlineKeyboardButton("🎴 Draw from Pile", callback_data="action:draw"),
        ],
        [
            InlineKeyboardButton("🏳️ Declare", callback_data="action:declare"),
        ],
        [
            InlineKeyboardButton(
                "⏬ Drop the Card",
                switch_inline_query_current_chat=f"@{bot_username} /drop "
            ),
        ],
        [
            InlineKeyboardButton("🃏 Card In Hand →", url=f"https://t.me/{bot_username}?start=hand"),
        ],
    ])


def turn_keyboard(game: dict = None) -> InlineKeyboardMarkup:
    """Legacy keyboard used only for the initial /startgame deal message.

    For all subsequent turns use persistent_game_keyboard() and edit
    the existing message instead of sending a new one.

    Returns:
        InlineKeyboardMarkup — identical to persistent_game_keyboard().
    """
    # Always return the full persistent layout; callers that previously
    # relied on phase-gating now use persistent_game_keyboard() directly.
    return persistent_game_keyboard()


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
