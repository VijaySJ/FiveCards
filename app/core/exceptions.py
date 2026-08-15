"""
exceptions.py — Custom exception classes for the 5 Cards game bot.

All game-specific exceptions inherit from GameException.
Each exception carries a user-facing message suitable for sending
directly to Telegram chat.
"""


class GameException(Exception):
    """Base exception for all 5 Cards game errors."""

    def __init__(self, message: str = "A game error occurred.") -> None:
        self.message = message
        super().__init__(self.message)


class GameNotFoundError(GameException):
    """Raised when no active game exists in the chat."""

    def __init__(self, message: str = "❌ No active game. Start one with /newgame.") -> None:
        super().__init__(message)


class NotYourTurnError(GameException):
    """Raised when a player tries to act out of turn."""

    def __init__(self, username: str = "") -> None:
        msg = f"⏳ It's not your turn! Wait for {username}." if username else "⏳ It's not your turn!"
        super().__init__(msg)


class InvalidCardError(GameException):
    """Raised when a player references a card they don't hold or that doesn't exist."""

    def __init__(self, card: str = "") -> None:
        msg = f"❌ You don't have {card} in your hand." if card else "❌ Invalid card."
        super().__init__(msg)


class InvalidActionError(GameException):
    """Raised when an action is invalid in the current game context."""

    def __init__(self, message: str = "❌ That action is not allowed right now.") -> None:
        super().__init__(message)


class WrongPhaseError(GameException):
    """Raised when a command is used during the wrong turn phase.

    Provides clear, contextual error messages based on what the player
    attempted and what they should do instead.
    """

    # Message templates for each invalid action → phase combination
    _MESSAGES: dict[tuple[str, str], str] = {
        # Tried to pick/draw/declare but should be dropping
        ("pick", "choose_action"):
            "⚠️ Drop a card first before picking!",
        ("draw", "choose_action"):
            "⚠️ Drop a card first before drawing!",
        ("declare", "choose_action"):
            "⚠️ You need to drop a card first before declaring!",
            
        # Tried to drop but should be picking/drawing
        ("drop", "must_discard"):
            "⚠️ You already dropped a card! Pick or draw now.",
    }

    def __init__(self, expected_phase: str = "", action: str = "") -> None:
        if action and expected_phase:
            key = (action, expected_phase)
            msg = self._MESSAGES.get(key)
            if msg:
                super().__init__(msg)
                return

        # Fallback messages
        if expected_phase == "choose_action":
            msg = "⚠️ Drop a card first!"
        elif expected_phase == "must_discard":
            msg = "⚠️ Pick a card or draw from the pile now!"
        else:
            msg = "🚫 You can't do that right now."
        super().__init__(msg)


class GameFullError(GameException):
    """Raised when a player tries to join a full game."""

    def __init__(self, max_players: int = 10) -> None:
        super().__init__(f"❌ Game is full (max {max_players} players).")


class PlayerNotFoundError(GameException):
    """Raised when a referenced player is not in the game."""

    def __init__(self, message: str = "❌ Player not found in this game.") -> None:
        super().__init__(message)


class AlreadyJoinedError(GameException):
    """Raised when a player tries to join a game they're already in."""

    def __init__(self) -> None:
        super().__init__("❌ You already joined this game.")


class GameAlreadyRunningError(GameException):
    """Raised when trying to start a new game while one is active."""

    def __init__(self, message: str = "❌ A game is already running in this group.") -> None:
        super().__init__(message)
