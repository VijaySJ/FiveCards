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


def persistent_game_keyboard(bot_username: str = "fivecardsbot", game: dict = None) -> InlineKeyboardMarkup:
    """Build the single persistent game keyboard shown throughout the game.

    This keyboard is sent ONCE at game start and the message is EDITED
    on every turn — it is NEVER re-sent as a new message.

    Buttons change dynamically based on the current turn phase.

    Returns:
        InlineKeyboardMarkup with action buttons.
    """
    buttons = []
    phase = game.get("turn_phase", "must_discard") if game else "must_discard"

    if phase != "must_draw":
        buttons.append([
            InlineKeyboardButton("🏳️ Declare", callback_data="action:declare"),
        ])
        buttons.append([
            InlineKeyboardButton(
                "⏬ Drop the Card",
                switch_inline_query_current_chat="/drop"
            ),
        ])
        buttons.append([
            InlineKeyboardButton("🃏 Card In Hand →", url=f"https://t.me/{bot_username}"),
        ])

    return InlineKeyboardMarkup(buttons)


def declare_confirm_keyboard() -> InlineKeyboardMarkup:
    """Build the confirmation keyboard shown when a player clicks Declare.
    
    Returns:
        InlineKeyboardMarkup with Yes/Cancel buttons.
    """
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes, Declare!", callback_data="confirm:declare"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel:declare"),
        ]
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
    return persistent_game_keyboard(game=game)


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


def must_draw_keyboard(game: dict = None, bot_username: str = "fivecardsbot") -> InlineKeyboardMarkup:
    """Build the keyboard shown under the 'No Match!' message.

    Provides the two actions available when a player must draw.
    """
    is_initial = game.get("is_initial_open_card", True) if game else True
    pick_label = "📥 Pick Open Card" if is_initial else "📥 Pick Dropped Card"
    
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 Card In Hand →", url=f"https://t.me/{bot_username}"),
        ],
        [
            InlineKeyboardButton(pick_label, callback_data="action:pick"),
            InlineKeyboardButton("🎴 Draw from Pile", callback_data="action:draw"),
        ]
    ])
