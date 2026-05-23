"""
test_card_utils.py — Unit tests for app.core.card_utils module.
"""

from app.core.card_utils import (
    create_single_deck,
    create_deck,
    shuffle_deck,
    deal_cards,
    get_card_rank,
    get_card_suit,
    card_point_value,
    hand_value,
    format_card,
    format_hand,
    is_joker_card,
    find_matching_rank_cards,
)


def test_single_deck_has_54_cards():
    """A single deck should have exactly 54 cards (52 + 2 jokers)."""
    deck = create_single_deck()
    assert len(deck) == 54


def test_no_duplicate_cards_in_single_deck():
    """Each card in a single deck should be unique."""
    deck = create_single_deck()
    assert len(deck) == len(set(deck))


def test_multi_deck_card_count():
    """Two decks should have 108 cards total."""
    deck = create_deck(2)
    assert len(deck) == 108


def test_multi_deck_jokers_unique():
    """Joker names should be unique across decks (JK1, JK2, JK3, JK4)."""
    deck = create_deck(2)
    jokers = [c for c in deck if is_joker_card(c)]
    assert len(jokers) == 4
    assert len(set(jokers)) == 4
    assert "JK1" in jokers
    assert "JK2" in jokers
    assert "JK3" in jokers
    assert "JK4" in jokers


def test_joker_point_value_is_zero():
    """Printed jokers (JK1, JK2) should always be worth 0 points."""
    assert card_point_value("JK1", "7") == 0
    assert card_point_value("JK2", "3") == 0


def test_open_joker_rank_is_zero():
    """Cards matching the joker_rank should be worth 0 points."""
    assert card_point_value("7H", "7") == 0
    assert card_point_value("7S", "7") == 0
    assert card_point_value("7D", "7") == 0
    assert card_point_value("7C", "7") == 0


def test_ace_is_1_point():
    """Aces should be worth 1 point (when not joker rank)."""
    assert card_point_value("AS", "7") == 1
    assert card_point_value("AH", "3") == 1


def test_king_is_13_points():
    """Kings should be worth 13 points (when not joker rank)."""
    assert card_point_value("KS", "7") == 13
    assert card_point_value("KH", "A") == 13


def test_face_cards():
    """J=11, Q=12, K=13 points."""
    assert card_point_value("JS", "7") == 11
    assert card_point_value("QH", "7") == 12
    assert card_point_value("KD", "7") == 13


def test_numbered_cards():
    """Numbered cards 2-10 should equal their face value."""
    assert card_point_value("2S", "7") == 2
    assert card_point_value("5H", "3") == 5
    assert card_point_value("10C", "A") == 10


def test_format_card_suits():
    """format_card should use ♠ ♥ ♣ ♦ symbols."""
    assert format_card("AS") == "A♠"
    assert format_card("6H") == "6♥"
    assert format_card("10C") == "10♣"
    assert format_card("KD") == "K♦"
    assert format_card("JK1") == "🃏"


def test_hand_value_calculation():
    """hand_value should sum up all card point values correctly."""
    hand = ["AS", "6H", "KD", "JK1", "10C"]
    # A=1, 6=6, K=13, JK=0, 10=10 = 30 (joker_rank != any of these)
    assert hand_value(hand, "7") == 30

    # With joker_rank = "6": A=1, 6=0, K=13, JK=0, 10=10 = 24
    assert hand_value(hand, "6") == 24


def test_hand_value_empty():
    """Empty hand should have value 0."""
    assert hand_value([], "7") == 0


def test_get_card_rank():
    """get_card_rank should extract the rank portion of a card."""
    assert get_card_rank("AS") == "A"
    assert get_card_rank("10C") == "10"
    assert get_card_rank("KH") == "K"
    assert get_card_rank("JK1") == "JK"


def test_get_card_suit():
    """get_card_suit should extract the suit character."""
    assert get_card_suit("AS") == "S"
    assert get_card_suit("10C") == "C"
    assert get_card_suit("KH") == "H"
    assert get_card_suit("JK1") == "JK"


def test_shuffle_does_not_mutate():
    """shuffle_deck should return a new list without modifying original."""
    deck = create_single_deck()
    original = list(deck)
    shuffled = shuffle_deck(deck)
    assert deck == original  # original unchanged
    assert set(shuffled) == set(deck)  # same cards


def test_deal_cards_correct_count():
    """deal_cards should give each player the correct number of cards."""
    deck = create_single_deck()
    shuffled = shuffle_deck(deck)
    hands, remaining = deal_cards(shuffled, 3, 5)
    assert len(hands) == 3
    for hand in hands:
        assert len(hand) == 5
    assert len(remaining) == 54 - 15  # 39 remaining


def test_find_matching_rank_cards():
    """find_matching_rank_cards should find all cards of a given rank."""
    hand = ["6H", "6D", "KS", "6C", "AS"]
    matches = find_matching_rank_cards(hand, "6")
    assert len(matches) == 3
    assert set(matches) == {"6H", "6D", "6C"}
