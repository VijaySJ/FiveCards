"""
game_engine.py — Core game logic for the 5 Cards game.

All functions are pure sync (no Telegram imports).
This module orchestrates card_utils and score_engine to implement
the full game flow: lobby → deal → turns → declare → next round.

Drop Rule:
  After picking a card (from discard or draw pile), the player
  MUST drop one or more cards from their hand. Multi-drop is allowed
  only when all dropped cards share the same rank.
  If the player's hand becomes empty after a drop, they score 0.
"""

import logging
import random
from typing import Optional

from app.core import card_utils
from app.core import score_engine
from app.config.settings import MAX_PLAYERS, CARDS_PER_PLAYER, get_num_decks
from app.core.exceptions import (
    GameFullError,
    InvalidActionError,
    InvalidCardError,
    NotYourTurnError,
    WrongPhaseError,
    AlreadyJoinedError,
    GameAlreadyRunningError,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# GAME LIFECYCLE
# ══════════════════════════════════════════════════════════════════


def create_new_game(chat_id: int, admin_id: int, admin_username: str, rounds: int) -> dict:
    """Create a fresh game state dict in 'waiting' status.

    Args:
        chat_id: Telegram group chat ID.
        admin_id: User ID of the game creator (admin).
        admin_username: Display name of the admin.
        rounds: Number of rounds to play (1-10).

    Returns:
        New game state dict ready for players to /join.
    """
    game: dict = {
        "chat_id": chat_id,
        "status": "waiting",
        "admin_id": admin_id,
        "rounds_total": rounds,
        "round_current": 0,
        "players": [],
        "deck": [],
        "discard_pile": [],
        "joker_rank": "",
        "current_turn_idx": 0,
        "declared_by_id": None,
        "turn_phase": "choose_action",
        "picked_card": None,
    }
    # Auto-add the admin as first player
    add_player(game, admin_id, admin_username)
    logger.info("New game created in chat %d by %s (%d rounds)", chat_id, admin_username, rounds)
    return game


def add_player(game: dict, user_id: int, username: str) -> None:
    """Add a player to a waiting game.

    Args:
        game: Game state dict (status must be "waiting").
        user_id: Telegram user ID.
        username: Display name.

    Raises:
        GameAlreadyRunningError: If the game has already started.
        AlreadyJoinedError: If the user is already in the game.
        GameFullError: If the game has MAX_PLAYERS players.
    """
    if game["status"] != "waiting":
        raise GameAlreadyRunningError()

    for p in game["players"]:
        if p["user_id"] == user_id:
            raise AlreadyJoinedError()

    if len(game["players"]) >= MAX_PLAYERS:
        raise GameFullError(MAX_PLAYERS)

    player: dict = {
        "user_id": user_id,
        "username": username,
        "hand": [],
        "round_scores": [],
        "total_score": 0,
    }
    game["players"].append(player)
    logger.info("Player %s (%d) joined game in chat %d", username, user_id, game["chat_id"])


def deal_initial_cards(game: dict) -> dict[int, list[str]]:
    """Deal cards to all players, set joker rank and open card.

    Args:
        game: Game state dict. Mutated in place.

    Returns:
        Dict mapping user_id → list of dealt cards (for DM sending).
    """
    num_players = len(game["players"])
    num_decks = get_num_decks(num_players)

    full_deck = card_utils.create_deck(num_decks)
    shuffled = card_utils.shuffle_deck(full_deck)
    hands, remaining = card_utils.deal_cards(shuffled, num_players, CARDS_PER_PLAYER)

    for i, player in enumerate(game["players"]):
        player["hand"] = hands[i]

    joker_card = remaining.pop(0)
    if card_utils.is_joker_card(joker_card):
        game["joker_rank"] = "JK"
    else:
        game["joker_rank"] = card_utils.get_card_rank(joker_card)

    open_card = remaining.pop(0)
    game["discard_pile"] = [open_card]
    game["deck"] = remaining

    game["status"] = "running"
    game["round_current"] = game.get("round_current", 0) + 1
    game["current_turn_idx"] = 0
    game["turn_phase"] = "choose_action"
    game["picked_card"] = None
    game["declared_by_id"] = None

    logger.info(
        "Dealt cards for round %d in chat %d: joker_rank=%s, open_card=%s, deck=%d cards",
        game["round_current"], game["chat_id"], game["joker_rank"],
        open_card, len(game["deck"]),
    )

    hands_map: dict[int, list[str]] = {}
    for player in game["players"]:
        hands_map[player["user_id"]] = list(player["hand"])
    return hands_map


# ══════════════════════════════════════════════════════════════════
# TURN ACTIONS
# ══════════════════════════════════════════════════════════════════


def validate_active_player(game: dict, player_id: int) -> dict:
    """Validate that it is the given player's turn.

    Args:
        game: Game state dict.
        player_id: User ID attempting the action.

    Returns:
        The active player dict.

    Raises:
        NotYourTurnError: If it's not this player's turn.
        InvalidActionError: If the game is not running.
    """
    if game["status"] != "running":
        raise InvalidActionError("❌ The game is not currently running.")
    active = game["players"][game["current_turn_idx"]]
    if active["user_id"] != player_id:
        raise NotYourTurnError(active["username"])
    return active


def process_pick(game: dict, player_id: int) -> str:
    """Player picks the top card from the discard pile.

    After picking, the player must drop a card (turn_phase → must_discard).
    The player always chooses what to drop — no automatic group-drop.

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the picking player.

    Returns:
        The picked card string.
    """
    player = validate_active_player(game, player_id)

    if game["turn_phase"] != "choose_action":
        raise WrongPhaseError("must_discard", action="pick")
    if not game["discard_pile"]:
        raise InvalidActionError("❌ Discard pile is empty!")

    picked = game["discard_pile"].pop()
    player["hand"].append(picked)
    game["picked_card"] = picked

    logger.info("Player %s picked %s from discard pile", player["username"], picked)

    game["turn_phase"] = "must_discard"
    return picked


def process_draw(game: dict, player_id: int) -> str:
    """Player draws the top card from the draw pile (deck).

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the drawing player.

    Returns:
        The drawn card string.
    """
    player = validate_active_player(game, player_id)

    if game["turn_phase"] != "choose_action":
        raise WrongPhaseError("must_discard", action="draw")

    if not game["deck"]:
        _reshuffle_discard_to_deck(game)

    drawn = game["deck"].pop(0)
    player["hand"].append(drawn)
    game["picked_card"] = drawn
    game["turn_phase"] = "must_discard"

    logger.info("Player %s drew %s from deck", player["username"], drawn)
    return drawn


def process_drop(game: dict, player_id: int, cards_to_drop: list[str]) -> bool:
    """Player discards one or more cards from their hand.

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the dropping player.
        cards_to_drop: List of card strings to discard.

    Returns:
        True if the player's hand is now empty.
    """
    player = validate_active_player(game, player_id)

    if game["turn_phase"] == "choose_action":
        # Direct drop (slip) rule: allowed only if dropping matches the top open card rank
        open_card = game["discard_pile"][-1]
        open_rank = card_utils.get_card_rank(open_card)
        drop_ranks = set(card_utils.get_card_rank(c.upper()) for c in cards_to_drop)
        if len(drop_ranks) != 1 or drop_ranks.pop() != open_rank:
            raise InvalidActionError("❌ You must pick a card first! Or drop a card that matches the open card's rank.")
    elif game["turn_phase"] != "must_discard":
        raise WrongPhaseError("choose_action", action="drop")
    if not cards_to_drop:
        raise InvalidActionError("❌ You must specify at least one card to drop.")

    hand_copy = list(player["hand"])
    for c in cards_to_drop:
        card_upper = c.upper()
        if card_upper not in hand_copy:
            raise InvalidCardError(c)
        hand_copy.remove(card_upper)

    if len(cards_to_drop) > 1:
        ranks = set(card_utils.get_card_rank(c.upper()) for c in cards_to_drop)
        if len(ranks) > 1:
            raise InvalidActionError("❌ All dropped cards must be the same rank.")

    for c in cards_to_drop:
        card_upper = c.upper()
        player["hand"].remove(card_upper)
        game["discard_pile"].append(card_upper)

    logger.info("Player %s dropped %s, %d cards remaining", player["username"], cards_to_drop, len(player["hand"]))

    hand_empty = len(player["hand"]) == 0
    game["picked_card"] = None
    advance_turn(game)
    return hand_empty


def process_timeout(game: dict, player_id: int) -> tuple[Optional[str], list[str], bool]:
    """Handle a player timing out their turn.
    
    If they haven't picked, draw a card for them. Then automatically drop a random card.
    
    Returns:
        (drawn_card, dropped_cards, hand_empty)
    """
    player = validate_active_player(game, player_id)
    drawn_card = None
    
    if game["turn_phase"] == "choose_action":
        if not game["deck"]:
            _reshuffle_discard_to_deck(game)
        drawn_card = game["deck"].pop(0)
        player["hand"].append(drawn_card)
        logger.info("Timeout: Player %s auto-drew %s", player["username"], drawn_card)
        game["turn_phase"] = "must_discard"
        
    # Auto drop a random card
    random_drop = random.choice(player["hand"])
    player["hand"].remove(random_drop)
    game["discard_pile"].append(random_drop)
    
    logger.info("Timeout: Player %s auto-dropped %s", player["username"], random_drop)
    
    hand_empty = len(player["hand"]) == 0
    game["picked_card"] = None
    advance_turn(game)
    
    return drawn_card, [random_drop], hand_empty


def process_declare(game: dict, player_id: int) -> dict[int, int]:
    """Player declares (attempts to win the round).

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the declaring player.

    Returns:
        Dict mapping user_id → points scored this round.
    """
    validate_active_player(game, player_id)

    if game["turn_phase"] != "choose_action":
        raise WrongPhaseError("must_discard", action="declare")

    game["declared_by_id"] = player_id
    game["status"] = "declaring"
    logger.info("Player %d declared in chat %d", player_id, game["chat_id"])

    round_scores = score_engine.calculate_round_scores(
        game["players"], player_id, game["joker_rank"]
    )
    score_engine.apply_round_scores(game, round_scores)
    return round_scores


# ══════════════════════════════════════════════════════════════════
# TURN MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def advance_turn(game: dict) -> None:
    """Advance the turn to the next player (wraps around).

    Args:
        game: Game state dict. Mutated in place.
    """
    num_players = len(game["players"])
    game["current_turn_idx"] = (game["current_turn_idx"] + 1) % num_players
    game["turn_phase"] = "choose_action"
    game["picked_card"] = None
    next_player = game["players"][game["current_turn_idx"]]
    logger.info("Turn advanced to %s (%d)", next_player["username"], next_player["user_id"])


def get_active_player(game: dict) -> dict:
    """Get the player dict for whose turn it currently is.

    Args:
        game: Game state dict.

    Returns:
        Active player dict.
    """
    return game["players"][game["current_turn_idx"]]


# ══════════════════════════════════════════════════════════════════
# ROUND MANAGEMENT
# ══════════════════════════════════════════════════════════════════


def is_game_over(game: dict) -> bool:
    """Check if all rounds have been played."""
    return game["round_current"] >= game["rounds_total"]


def start_next_round(game: dict) -> dict[int, list[str]]:
    """Re-deal cards for the next round with a new deck and joker.

    Args:
        game: Game state dict. Mutated in place.

    Returns:
        Dict mapping user_id → list of new cards.
    """
    for player in game["players"]:
        player["hand"] = []
    game["deck"] = []
    game["discard_pile"] = []
    game["declared_by_id"] = None
    game["status"] = "running"
    logger.info("Starting round %d in chat %d", game["round_current"] + 1, game["chat_id"])
    return deal_initial_cards(game)


def end_game(game: dict) -> str:
    """End the game and build the final leaderboard.

    Args:
        game: Game state dict. Mutated in place.

    Returns:
        Formatted leaderboard string.
    """
    game["status"] = "ended"
    leaderboard = score_engine.build_leaderboard(game)
    logger.info("Game ended in chat %d", game["chat_id"])
    return leaderboard


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ══════════════════════════════════════════════════════════════════


def _reshuffle_discard_to_deck(game: dict) -> None:
    """Reshuffle the discard pile into a new draw deck.

    Args:
        game: Game state dict. Mutated in place.
    """
    if len(game["discard_pile"]) <= 1:
        logger.warning("Cannot reshuffle — discard pile has %d cards", len(game["discard_pile"]))
        return

    top_card = game["discard_pile"].pop()
    cards_to_shuffle = list(game["discard_pile"])
    game["discard_pile"] = [top_card]
    game["deck"] = card_utils.shuffle_deck(cards_to_shuffle)
    logger.info("Reshuffled %d cards from discard pile into deck", len(game["deck"]))
