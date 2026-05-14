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

import html
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
    game["turn_phase"] = "must_discard"
    game["picked_card"] = None
    game["declared_by_id"] = None
    game["cards_dropped_this_turn"] = 0

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

    After picking, the player's turn ends.

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the picking player.

    Returns:
        The picked card string.
    """
    player = validate_active_player(game, player_id)

    if game["turn_phase"] != "must_draw":
        raise WrongPhaseError("must_draw", action="pick")
    
    cards_dropped = game.get("cards_dropped_this_turn", 0)
    if len(game["discard_pile"]) <= cards_dropped:
        raise InvalidActionError("❌ No open card to pick!")

    dropped_cards = []
    for _ in range(cards_dropped):
        dropped_cards.append(game["discard_pile"].pop())

    picked = game["discard_pile"].pop()
    player["hand"].append(picked)
    
    for card in reversed(dropped_cards):
        game["discard_pile"].append(card)

    safe_name = html.escape(player['username'])
    game["last_action"] = f"📥 {safe_name} picked the open card"
    game["picked_card"] = picked
    game["cards_dropped_this_turn"] = 0
    logger.info("Player %s picked %s from discard pile", player["username"], picked)
    advance_turn(game)
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

    if game["turn_phase"] != "must_draw":
        raise WrongPhaseError("must_draw", action="draw")

    if not game["deck"]:
        _reshuffle_discard_to_deck(game)

    drawn = game["deck"].pop(0)
    player["hand"].append(drawn)
    safe_name = html.escape(player['username'])
    game["last_action"] = f"🎴 {safe_name} drew from the pile"
    game["picked_card"] = drawn
    game["cards_dropped_this_turn"] = 0
    logger.info("Player %s drew %s from deck", player["username"], drawn)
    advance_turn(game)
    return drawn


def parse_drop_tokens(tokens: list[str]) -> list[str]:
    """Parse drop command tokens into canonical rank strings.

    Accepts rank-only tokens like ['9','9'] or ['K','K','K']
    or old suit-suffixed tokens like ['9H','9S'] — suit is ignored.

    Args:
        tokens: Raw string tokens from the /drop command.

    Returns:
        List of canonical rank strings e.g. ['9','9'].

    Raises:
        InvalidCardError: If a token cannot be mapped to a valid rank.
    """
    rank_map: dict[str, str] = {
        '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
        '7': '7', '8': '8', '9': '9', '10': '10',
        'j': 'J', 'q': 'Q', 'k': 'K', 'a': 'A',
        'jack': 'J', 'queen': 'Q', 'king': 'K', 'ace': 'A',
        'jk': 'JK',  # printed joker rank
    }
    ranks: list[str] = []
    for token in tokens:
        t = token.strip().lower()
        # Strip any trailing suit character (c/h/d/s) so '9h' → '9'
        if len(t) > 1 and t[-1] in ('c', 'h', 'd', 's') and not t.startswith('jk'):
            t = t[:-1]
        rank = rank_map.get(t)
        if rank is None:
            raise InvalidCardError(
                f"❌ Unknown card: {token}\n"
                f"Use rank only: /drop 9 9  or  /drop K K K"
            )
        ranks.append(rank)
    return ranks


def process_drop(game: dict, player_id: int, tokens: list[str]) -> dict:
    """Player discards one or more cards from their hand by rank.

    Args:
        game:     Game state dict. Mutated in place.
        player_id: User ID of the dropping player.
        tokens:   Raw token strings from the /drop command.

    Returns:
        A dict containing 'is_direct_drop', 'hand_empty', 'dropped', and 'remaining'.
    """
    player = validate_active_player(game, player_id)

    if game["turn_phase"] != "must_discard":
        raise WrongPhaseError("must_discard", action="drop")
    if not tokens:
        raise InvalidActionError("❌ You must specify at least one card to drop.")

    drop_ranks = parse_drop_tokens(tokens)

    # All tokens must be the same rank
    if len(set(drop_ranks)) > 1:
        raise InvalidActionError(
            "❌ All dropped cards must be the same rank.\n"
            "Example: /drop 9 9"
        )

    target_rank = drop_ranks[0]
    count_to_drop = len(drop_ranks)

    matching_cards = [
        c for c in player["hand"]
        if card_utils.get_card_rank(c) == target_rank
    ]

    if len(matching_cards) < count_to_drop:
        raise InvalidCardError(
            f"❌ You only have {len(matching_cards)} card(s) of rank {target_rank}\n"
            f"in your hand. You tried to drop {count_to_drop}."
        )

    cards_to_remove = matching_cards[:count_to_drop]
    
    # Record previous open card BEFORE adding new ones
    prev_open_card = game["discard_pile"][-1] if game["discard_pile"] else None
    
    for card in cards_to_remove:
        player["hand"].remove(card)
        game["discard_pile"].append(card)
        
    game["cards_dropped_this_turn"] = count_to_drop

    logger.info(
        "Player %s dropped %s (%d card(s)), %d remaining",
        player["username"], cards_to_remove, count_to_drop, len(player["hand"]),
    )

    # Check direct drop: dropped rank matches previous open card's rank
    is_direct_drop = False
    if prev_open_card:
        prev_rank = card_utils.get_card_rank(prev_open_card)
        if target_rank == prev_rank:
            is_direct_drop = True

    game["picked_card"] = None

    # NEW RULES:
    # 1. If Match (Direct Drop) -> Turn ends.
    # 2. If Hand Empty -> Turn ends.
    # 3. If NO Match -> Must Draw.
    should_advance = is_direct_drop or not player["hand"]

    if should_advance:
        safe_name = html.escape(player['username'])
        if is_direct_drop:
            game["last_action"] = f"🎯 {safe_name} made a DIRECT DROP!"
        elif not player["hand"]:
            game["last_action"] = f"✨ {safe_name} finished their turn (0 cards left)"
        advance_turn(game)
    else:
        safe_name = html.escape(player['username'])
        game["last_action"] = f"👤 {safe_name} dropped {len(cards_to_remove)} card(s)"
        game["turn_phase"] = "must_draw"

    return {
        "is_direct_drop": is_direct_drop,
        "hand_empty": len(player["hand"]) == 0,
        "dropped": cards_to_remove,
        "remaining": len(player["hand"]),
        "turn_advanced": should_advance
    }


def process_timeout(game: dict, player_id: int) -> tuple[Optional[str], list[str], bool]:
    """Handle a player timing out their turn."""
    player = validate_active_player(game, player_id)

    if len(player["hand"]) == 0:
        game["pending_auto_declare"] = player_id
        advance_turn(game)
        return None, [], True

    drawn_card = None
    dropped_cards = []
    
    if game["turn_phase"] == "must_discard":
        card_to_drop = random.choice(player["hand"])
        prev_open_card = game["discard_pile"][-1] if game["discard_pile"] else None
        
        player["hand"].remove(card_to_drop)
        game["discard_pile"].append(card_to_drop)
        dropped_cards = [card_to_drop]
        
        is_direct_drop = False
        if prev_open_card:
            open_rank = card_utils.get_card_rank(prev_open_card)
            drop_rank = card_utils.get_card_rank(card_to_drop)
            if drop_rank == open_rank:
                is_direct_drop = True
                
        safe_name = html.escape(player['username'])
        if is_direct_drop or not player["hand"]:
            if is_direct_drop:
                game["last_action"] = f"⏰ {safe_name} timed out (Direct Drop)"
            else:
                game["last_action"] = f"⏰ {safe_name} timed out (Finished)"
            advance_turn(game)
            return None, dropped_cards, not player["hand"]
        else:
            # Phase changed to must_draw
            game["last_action"] = f"⏰ {safe_name} timed out (Must Draw)"
            game["turn_phase"] = "must_draw"
            game["picked_card"] = None
            return None, dropped_cards, False

    elif game["turn_phase"] == "must_draw":
        if not game["deck"]:
            _reshuffle_discard_to_deck(game)
        drawn_card = game["deck"].pop(0)
        player["hand"].append(drawn_card)
        game["last_action"] = f"⏰ {player['username']} timed out (Auto Draw)"
        advance_turn(game)
        
    game["picked_card"] = None
    return drawn_card, dropped_cards, not player["hand"]


def process_declare(game: dict, player_id: int) -> dict[int, int]:
    """Player declares (attempts to win the round).

    Declaration is only allowed at the START of a player's turn,
    i.e. when turn_phase == "must_discard" (before picking/drawing).

    Args:
        game: Game state dict. Mutated in place.
        player_id: User ID of the declaring player.

    Returns:
        Dict mapping user_id → points scored this round.
    """
    validate_active_player(game, player_id)

    # CHANGE #4 FIX: declare is valid at the START of a turn (must_discard),
    # NOT after pick/draw (choose_action). The old check was inverted.
    if game["turn_phase"] != "must_discard":
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

    If the next player has 0 cards in hand, sets game["pending_auto_declare"]
    so start_turn_timer() can immediately trigger a declare for them.

    Args:
        game: Game state dict. Mutated in place.
    """
    num_players = len(game["players"])
    game["current_turn_idx"] = (game["current_turn_idx"] + 1) % num_players
    game["turn_phase"] = "must_discard"
    game["picked_card"] = None
    game["cards_dropped_this_turn"] = 0
    next_player = game["players"][game["current_turn_idx"]]
    logger.info("Turn advanced to %s (%d)", next_player["username"], next_player["user_id"])

    # FIX #7: Auto-declare if next player already has 0 cards
    if len(next_player["hand"]) == 0:
        game["pending_auto_declare"] = next_player["user_id"]
        logger.info("Player %s has 0 cards — flagging pending_auto_declare", next_player["username"])



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


def get_ranks_in_hand(hand: list[str]) -> list[str]:
    """Return a list of unique ranks present in the given hand."""
    from app.core.card_utils import get_card_rank
    return list(set(get_card_rank(c) for c in hand))