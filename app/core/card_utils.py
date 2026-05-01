"""
card_utils.py — Deck creation, shuffling, dealing, and point calculations.

All functions are pure (no side effects on external state) and have
no Telegram imports. Cards are represented as plain strings.

Card format:
  Regular cards : RANK + SUIT  e.g. "AS", "10C", "KH"
  Printed jokers: "JK1", "JK2", "JK3", "JK4" ... (numbered per deck)
"""

import copy
import random
import logging
from typing import Optional

from app.config.settings import RANKS, SUITS, SUIT_SYMBOLS, RANK_POINTS

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# DECK CREATION
# ══════════════════════════════════════════════════════════════════


def create_single_deck(deck_index: int = 0) -> list[str]:
    """Create a single 54-card deck (52 suited cards + 2 printed jokers).

    Args:
        deck_index: Zero-based index of this deck.  Jokers are named
                    JK1/JK2 for deck 0, JK3/JK4 for deck 1, etc.

    Returns:
        List of 54 card strings.
    """
    cards: list[str] = []
    for rank in RANKS:
        for suit in SUITS:
            cards.append(f"{rank}{suit}")
    # Printed jokers — unique names across multiple decks
    jk_base = deck_index * 2 + 1
    cards.append(f"JK{jk_base}")
    cards.append(f"JK{jk_base + 1}")
    return cards


def create_deck(num_decks: int = 1) -> list[str]:
    """Create a combined deck from one or more 54-card decks.

    When using multiple decks, regular cards (e.g. "AS") will appear
    multiple times.  Jokers are uniquely numbered across all decks.

    Args:
        num_decks: Number of 54-card decks to combine.

    Returns:
        Combined list of cards (54 * num_decks total).
    """
    full_deck: list[str] = []
    for i in range(num_decks):
        full_deck.extend(create_single_deck(deck_index=i))
    logger.info("Created deck with %d decks (%d cards total)", num_decks, len(full_deck))
    return full_deck


def shuffle_deck(deck: list[str]) -> list[str]:
    """Return a shuffled copy of the deck. Does not mutate the original.

    Args:
        deck: List of card strings.

    Returns:
        New shuffled list.
    """
    shuffled = copy.copy(deck)
    random.shuffle(shuffled)
    return shuffled


def deal_cards(
    deck: list[str], num_players: int, cards_each: int = 5
) -> tuple[list[list[str]], list[str]]:
    """Deal cards from the deck in round-robin order.

    Args:
        deck: The draw pile (will be mutated — cards removed from front).
        num_players: Number of players to deal to.
        cards_each: Cards dealt to each player.

    Returns:
        Tuple of (hands, remaining_deck) where hands is a list of
        lists — one hand per player index.
    """
    hands: list[list[str]] = [[] for _ in range(num_players)]
    remaining = list(deck)  # shallow copy to avoid mutating input

    for _ in range(cards_each):
        for p in range(num_players):
            if remaining:
                hands[p].append(remaining.pop(0))

    logger.info(
        "Dealt %d cards each to %d players, %d cards remaining",
        cards_each, num_players, len(remaining),
    )
    return hands, remaining


# ══════════════════════════════════════════════════════════════════
# CARD PARSING
# ══════════════════════════════════════════════════════════════════


def is_joker_card(card: str) -> bool:
    """Check if a card is a printed joker (JK1, JK2, JK3, ...).

    Args:
        card: Card string.

    Returns:
        True if the card is a printed joker.
    """
    return card.startswith("JK")


def get_card_rank(card: str) -> str:
    """Extract the rank from a card string.

    Args:
        card: Card string, e.g. "10C", "AS", "JK1".

    Returns:
        Rank string: "10", "A", "JK", etc.
    """
    if is_joker_card(card):
        return "JK"
    # Ranks can be 1 or 2 chars ("A" through "9" = 1 char, "10" = 2 chars)
    return card[:-1]  # everything except the last char (suit)


def get_card_suit(card: str) -> str:
    """Extract the suit from a card string.

    Args:
        card: Card string, e.g. "10C", "AS", "JK1".

    Returns:
        Suit character: "S", "H", "C", "D", or "JK" for jokers.
    """
    if is_joker_card(card):
        return "JK"
    return card[-1]  # last character


# ══════════════════════════════════════════════════════════════════
# POINT CALCULATIONS
# ══════════════════════════════════════════════════════════════════


def card_point_value(card: str, joker_rank: str) -> int:
    """Calculate the point value of a single card.

    Rules:
      - Printed jokers (JK1, JK2, ...) → 0 points
      - Cards whose rank matches joker_rank → 0 points (open joker)
      - A = 1, 2-10 = face value, J = 11, Q = 12, K = 13

    Args:
        card: Card string.
        joker_rank: The rank designated as joker for this round.

    Returns:
        Integer point value.
    """
    if is_joker_card(card):
        return 0
    rank = get_card_rank(card)
    if rank == joker_rank:
        return 0
    return RANK_POINTS.get(rank, 0)


def hand_value(hand: list[str], joker_rank: str) -> int:
    """Calculate the total point value of a hand.

    Args:
        hand: List of card strings.
        joker_rank: The rank designated as joker for this round.

    Returns:
        Sum of point values.
    """
    return sum(card_point_value(c, joker_rank) for c in hand)


# ══════════════════════════════════════════════════════════════════
# CARD FORMATTING (for display)
# ══════════════════════════════════════════════════════════════════


def format_card(card: str) -> str:
    """Format a card for human-readable display with suit symbols.

    Examples:
      "6H" → "6♥"
      "AS" → "A♠"
      "10C" → "10♣"
      "JK1" → "🃏"

    Args:
        card: Card string.

    Returns:
        Formatted display string.
    """
    if is_joker_card(card):
        return "🃏"
    rank = get_card_rank(card)
    suit = get_card_suit(card)
    symbol = SUIT_SYMBOLS.get(suit, suit)
    return f"{rank}{symbol}"


def format_hand(hand: list[str], joker_rank: str) -> str:
    """Format a complete hand with card display and point values.

    Example output:
      "A♠(1)  6♥(0)  K♦(13)  J♣(11)  🃏(0)  →  Total: 25 pts"

    Args:
        hand: List of card strings.
        joker_rank: Current round's joker rank.

    Returns:
        Formatted hand string with per-card points and total.
    """
    if not hand:
        return "🫗 Empty hand  →  Total: 0 pts"

    parts: list[str] = []
    for card in hand:
        display = format_card(card)
        pts = card_point_value(card, joker_rank)
        parts.append(f"{display}({pts})")

    total = hand_value(hand, joker_rank)
    return "  ".join(parts) + f"  →  Total: {total} pts"


def find_matching_rank_cards(hand: list[str], target_rank: str) -> list[str]:
    """Find all cards in a hand that match a given rank.

    Args:
        hand: List of card strings.
        target_rank: Rank to search for (e.g. "6", "K", "JK").

    Returns:
        List of cards from hand that have the target rank.
    """
    return [c for c in hand if get_card_rank(c) == target_rank]
