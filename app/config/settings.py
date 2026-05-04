"""
settings.py — Configuration and constants for the 5 Cards game bot.

Loads environment variables from a .env file and exposes
game constants used across the project.
"""

import math
import os
import logging

from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# ── Bot token (required) ──────────────────────────────────────────
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ── Bot & Group links (for navigation buttons) ───────────────────
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "fivecardsbot")
GROUP_LINK: str = os.getenv("GROUP_LINK", "https://t.me/TamilChatRockers_world")

# ── Game constants ────────────────────────────────────────────────
MAX_PLAYERS: int = int(os.getenv("MAX_PLAYERS", "10"))
DEFAULT_ROUNDS: int = int(os.getenv("DEFAULT_ROUNDS", "3"))
MAX_ROUNDS: int = int(os.getenv("MAX_ROUNDS", "10"))
CARDS_PER_PLAYER: int = int(os.getenv("CARDS_PER_PLAYER", "5"))

# ── Card constants ────────────────────────────────────────────────
RANKS: list[str] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS: list[str] = ["S", "H", "C", "D"]

SUIT_SYMBOLS: dict[str, str] = {
    "S": "♠",
    "H": "♥",
    "C": "♣",
    "D": "♦",
}

# Point value map for non-numeric ranks
RANK_POINTS: dict[str, int] = {
    "A": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
    "9": 9,
    "10": 10,
    "J": 11,
    "Q": 12,
    "K": 13,
}

# Penalty score for failed declaration
DECLARATION_PENALTY: int = 80

# ── Logging ───────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    format="%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)


def get_num_decks(player_count: int) -> int:
    """Calculate how many 54-card decks are needed for the given player count.

    Formula: ceil(player_count / 7)
      - 2–7 players → 1 deck  (54 cards)
      - 8–10 players → 2 decks (108 cards)

    This ensures a comfortable draw pile (≥ 10 cards) after dealing
    5 cards to each player plus the joker-reveal and open cards.

    Args:
        player_count: Number of players in the game (2-10).

    Returns:
        Number of 54-card decks to use.
    """
    return max(1, math.ceil(player_count / 7))
