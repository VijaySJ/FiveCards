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
        msg = f"⏳ Wait for your turn, {username}!" if username else "⏳ It's not your turn!"
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
    """Raised when a command is used during the wrong turn phase."""

    def __init__(self, expected_phase: str = "") -> None:
        if expected_phase == "must_discard":
            msg = "🚫 You need to /drop a card first."
        elif expected_phase == "choose_action":
            msg = "🚫 You need to /pick, /draw, or /declare first."
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

    def __init__(self) -> None:
        super().__init__("❌ A game is already running in this group.")
