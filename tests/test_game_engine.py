"""
test_game_engine.py — Unit tests for app.core.game_engine module.
"""

import pytest

from app.core.game_engine import (
    create_new_game,
    add_player,
    deal_initial_cards,
    process_pick,
    process_draw,
    process_drop,
    process_declare,
    advance_turn,
    get_active_player,
    _reshuffle_discard_to_deck,
)
from app.core.exceptions import (
    GameFullError,
    NotYourTurnError,
    WrongPhaseError,
    AlreadyJoinedError,
    InvalidCardError,
    InvalidActionError,
)


def _make_test_game(num_players: int = 3) -> dict:
    """Create a test game with the given number of players and deal cards."""
    game = create_new_game(chat_id=12345, admin_id=1, admin_username="Player1", rounds=2)
    for i in range(2, num_players + 1):
        add_player(game, i, f"Player{i}")
    deal_initial_cards(game)
    return game


def test_deal_gives_5_cards_each():
    """After dealing, each player should have exactly 5 cards."""
    game = _make_test_game(3)
    for player in game["players"]:
        assert len(player["hand"]) == 5


def test_joker_rank_set_after_deal():
    """joker_rank should be set to a non-empty string after dealing."""
    game = _make_test_game(3)
    assert game["joker_rank"] != ""
    assert isinstance(game["joker_rank"], str)


def test_open_card_set_after_deal():
    """discard_pile should have exactly one card (the open card) after deal."""
    game = _make_test_game(3)
    assert len(game["discard_pile"]) == 1


def test_group_drop_clears_matching_cards():
    """When picking a card and holding 2+ of the same rank, group drop fires."""
    game = _make_test_game(3)
    player = game["players"][0]
    player["hand"] = ["6H", "6D", "KS", "3C", "AS"]
    game["discard_pile"] = ["9H", "6C"]
    game["current_turn_idx"] = 0
    game["turn_phase"] = "choose_action"

    picked_card, group_dropped = process_pick(game, player["user_id"])

    assert picked_card == "6C"
    assert group_dropped is not None
    assert len(group_dropped) == 3
    assert len(player["hand"]) == 3
    assert "6H" not in player["hand"]
    assert "6D" not in player["hand"]
    assert "6C" not in player["hand"]


def test_group_drop_with_4_matching_cards():
    """Group drop should work with 4+ matching cards (multi-deck scenario)."""
    game = _make_test_game(3)
    player = game["players"][0]
    player["hand"] = ["6H", "6D", "6S", "KS", "AS"]
    game["discard_pile"] = ["9H", "6C"]
    game["current_turn_idx"] = 0
    game["turn_phase"] = "choose_action"

    picked_card, group_dropped = process_pick(game, player["user_id"])

    assert picked_card == "6C"
    assert group_dropped is not None
    assert len(group_dropped) == 4
    assert len(player["hand"]) == 2


def test_advance_turn_wraps_around():
    """advance_turn should wrap from last player back to first."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 2

    advance_turn(game)

    assert game["current_turn_idx"] == 0
    assert game["turn_phase"] == "choose_action"
    assert game["picked_card"] is None


def test_not_your_turn_error():
    """Attempting an action out of turn should raise NotYourTurnError."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0

    with pytest.raises(NotYourTurnError):
        process_draw(game, 2)


def test_wrong_phase_draw_after_draw():
    """After drawing, pick/draw should raise WrongPhaseError (must_discard)."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0
    game["turn_phase"] = "choose_action"

    process_draw(game, 1)
    game["current_turn_idx"] = 0

    with pytest.raises(WrongPhaseError):
        process_pick(game, 1)

    with pytest.raises(WrongPhaseError):
        process_draw(game, 1)


def test_empty_deck_reshuffles_discard():
    """Drawing from an empty deck should auto-reshuffle the discard pile."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0
    game["turn_phase"] = "choose_action"

    game["deck"] = []
    game["discard_pile"] = ["3H", "5C", "7D", "9S", "JS"]

    drawn = process_draw(game, 1)

    assert drawn is not None
    assert isinstance(drawn, str)


def test_drop_validates_cards_in_hand():
    """Dropping a card not in hand should raise InvalidCardError."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0
    game["turn_phase"] = "must_discard"
    game["players"][0]["hand"] = ["AS", "6H", "KD", "3C", "10S", "JK1"]

    with pytest.raises(InvalidCardError):
        process_drop(game, 1, ["QH"])


def test_multi_drop_same_rank_only():
    """Multi-drop must have all cards of the same rank."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0
    game["turn_phase"] = "must_discard"
    game["players"][0]["hand"] = ["6H", "6D", "KD", "3C", "10S", "AS"]

    with pytest.raises(InvalidActionError):
        process_drop(game, 1, ["6H", "KD"])


def test_valid_multi_drop():
    """Multi-drop with same rank cards should work."""
    game = _make_test_game(3)
    game["current_turn_idx"] = 0
    game["turn_phase"] = "must_discard"
    game["players"][0]["hand"] = ["6H", "6D", "KD", "3C", "10S", "AS"]

    hand_empty = process_drop(game, 1, ["6H", "6D"])

    assert hand_empty is False
    assert "6H" not in game["players"][0]["hand"]
    assert "6D" not in game["players"][0]["hand"]
    assert len(game["players"][0]["hand"]) == 4
