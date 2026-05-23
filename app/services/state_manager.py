"""
state_manager.py — In-memory game state CRUD operations.

Stores all active games in a global Python dict keyed by chat_id.
This is sufficient for a single-process polling bot.

NOTE (scaling): For multi-process or webhook deployments, replace
GAMES with a Redis hash store.  Each function here would then
become a Redis GET/SET/DEL call.  The function signatures can
remain identical.
"""

import logging
from typing import Optional

from app.core.exceptions import GameNotFoundError, PlayerNotFoundError

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# GLOBAL STATE
# Thread-safe for single-process asyncio (single thread of execution).
# For multi-process: replace with Redis or another external store.
# ══════════════════════════════════════════════════════════════════

GAMES: dict[int, dict] = {}


# ══════════════════════════════════════════════════════════════════
# GAME-LEVEL CRUD
# ══════════════════════════════════════════════════════════════════


def create_game(chat_id: int, game: dict) -> dict:
    """Store a new game state for a chat.

    Args:
        chat_id: Telegram group chat ID.
        game: Complete game state dict.

    Returns:
        The stored game dict.
    """
    GAMES[chat_id] = game
    logger.info("Game created for chat %d", chat_id)
    return game





def get_game(chat_id: int) -> Optional[dict]:
    """Retrieve the game state for a chat, or None if no game exists.

    Args:
        chat_id: Telegram group chat ID.

    Returns:
        Game state dict or None.
    """
    return GAMES.get(chat_id)


def get_game_or_raise(chat_id: int) -> dict:
    """Retrieve the game state for a chat, raising if not found.

    Args:
        chat_id: Telegram group chat ID.

    Returns:
        Game state dict.

    Raises:
        GameNotFoundError: If no game exists for this chat.
    """
    game = GAMES.get(chat_id)
    if game is None:
        raise GameNotFoundError()
    return game


def update_game(chat_id: int, game: dict) -> None:
    """Update the stored game state.

    Args:
        chat_id: Telegram group chat ID.
        game: Updated game state dict.
    """
    GAMES[chat_id] = game


def delete_game(chat_id: int) -> None:
    """Remove the game state for a chat.

    Args:
        chat_id: Telegram group chat ID.
    """
    if chat_id in GAMES:
        del GAMES[chat_id]
        logger.info("Game deleted for chat %d", chat_id)


def game_exists(chat_id: int) -> bool:
    """Check whether an active game exists for a chat.

    Args:
        chat_id: Telegram group chat ID.

    Returns:
        True if a game exists.
    """
    return chat_id in GAMES


# ══════════════════════════════════════════════════════════════════
# PLAYER-LEVEL QUERIES
# ══════════════════════════════════════════════════════════════════


def get_player(game: dict, user_id: int) -> Optional[dict]:
    """Find a player in the game by user_id.

    Args:
        game: Game state dict.
        user_id: Telegram user ID.

    Returns:
        Player dict or None if not found.
    """
    for player in game["players"]:
        if player["user_id"] == user_id:
            return player
    return None


def get_player_or_raise(game: dict, user_id: int) -> dict:
    """Find a player in the game by user_id, raising if not found.

    Args:
        game: Game state dict.
        user_id: Telegram user ID.

    Returns:
        Player dict.

    Raises:
        PlayerNotFoundError: If the user is not in the game.
    """
    player = get_player(game, user_id)
    if player is None:
        raise PlayerNotFoundError()
    return player


def is_active_player(game: dict, user_id: int) -> bool:
    """Check if it is the given user's turn.

    Args:
        game: Game state dict.
        user_id: Telegram user ID.

    Returns:
        True if user_id matches the current turn player.
    """
    if game["status"] != "running":
        return False
    idx = game["current_turn_idx"]
    if 0 <= idx < len(game["players"]):
        return game["players"][idx]["user_id"] == user_id
    return False


def get_active_player(game: dict) -> Optional[dict]:
    """Get the player dict for whoever's turn it currently is.

    Args:
        game: Game state dict.

    Returns:
        Active player dict, or None if game is not running.
    """
    if game["status"] != "running":
        return None
    idx = game["current_turn_idx"]
    if 0 <= idx < len(game["players"]):
        return game["players"][idx]
    return None


def find_game_by_user_id(user_id: int) -> Optional[tuple[int, dict]]:
    """Find an active game that the given user is part of.

    Returns:
        Tuple of (chat_id, game_dict) or None.
    """
    for chat_id, game in GAMES.items():
        for player in game["players"]:
            if player["user_id"] == user_id:
                return chat_id, game
    return None
