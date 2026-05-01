"""
test_score_engine.py — Unit tests for app.core.score_engine module.

Verifies all 4 scoring rules from Section 4F, including the
priority of RULE 2 over RULE 3, and the Vijay/Ravi/Meena scenario
from Section 13.
"""

from app.core.score_engine import calculate_round_scores, apply_round_scores, build_leaderboard


def _make_players(hands: dict[int, list[str]]) -> list[dict]:
    """Helper to create player dicts for testing."""
    players = []
    for uid, hand in hands.items():
        players.append({
            "user_id": uid,
            "username": f"Player{uid}",
            "hand": hand,
            "round_scores": [],
            "total_score": 0,
        })
    return players


def test_declarer_lowest_gets_zero():
    """RULE 1: Declarer with strictly lowest hand value gets 0 points."""
    players = _make_players({
        1: ["AS", "2S"],           # value = 1+2 = 3 (declarer)
        2: ["KS", "QH"],          # value = 13+12 = 25
        3: ["10C", "JD"],         # value = 10+11 = 21
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="7")

    assert scores[1] == 0    # declarer gets 0
    assert scores[2] == 25   # others get their hand value
    assert scores[3] == 21


def test_declarer_not_lowest_gets_80():
    """RULE 2: If any opponent has lower hand value, declarer gets 80 penalty."""
    players = _make_players({
        1: ["KS", "QH"],          # value = 13+12 = 25 (declarer)
        2: ["AS", "2S"],          # value = 1+2 = 3 (lower!)
        3: ["10C", "JD"],         # value = 10+11 = 21
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="7")

    assert scores[1] == 80   # declarer gets penalty
    assert scores[2] == 3    # others get their hand value
    assert scores[3] == 21


def test_tie_with_declarer_both_get_zero():
    """RULE 3: Tied opponent and declarer both get 0 (when no one is lower)."""
    players = _make_players({
        1: ["AS", "2S"],           # value = 3 (declarer)
        2: ["AS", "2H"],          # value = 3 (tied!)
        3: ["10C", "JD"],         # value = 21
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="7")

    assert scores[1] == 0    # declarer tied → 0
    assert scores[2] == 0    # tied opponent → 0
    assert scores[3] == 21   # others get their hand value


def test_tie_and_lower_rule2_overrides():
    """RULE 2 overrides RULE 3: declarer gets 80 even if someone ties,
    if another opponent has a lower value."""
    players = _make_players({
        1: ["5S", "5H"],           # value = 10 (declarer)
        2: ["5C", "5D"],          # value = 10 (tied!)
        3: ["AS", "2S"],          # value = 3 (LOWER!)
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="7")

    assert scores[1] == 80   # RULE 2: declarer gets penalty
    assert scores[2] == 0    # tied player still gets 0
    assert scores[3] == 3    # lower player gets their value


def test_empty_hand_always_zero():
    """RULE 4: Player with empty hand always scores 0 regardless of other rules."""
    players = _make_players({
        1: ["KS", "QH"],          # value = 25 (declarer)
        2: [],                     # empty hand → 0
        3: ["10C", "JD"],         # value = 21
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="7")

    assert scores[1] == 80   # declarer penalty (someone has lower)
    assert scores[2] == 0    # empty hand → 0
    assert scores[3] == 21


def test_joker_rank_cards_worth_zero_in_scoring():
    """Cards matching joker_rank should be treated as 0 points in scoring."""
    players = _make_players({
        1: ["6H", "6D", "AS"],     # value = 0+0+1 = 1 (declarer)
        2: ["KS", "QH"],          # value = 13+12 = 25
        3: ["10C", "JD"],         # value = 10+11 = 21
    })
    scores = calculate_round_scores(players, declared_by_id=1, joker_rank="6")

    assert scores[1] == 0    # lowest → 0
    assert scores[2] == 25
    assert scores[3] == 21


def test_section13_scenario():
    """Verify the exact scoring scenario from Section 13."""
    players = _make_players({
        1: ["KS", "3C", "AS"],            # Vijay: 13+3+1 = 17
        2: ["2H", "4D", "7S", "JC", "QH"],  # Ravi: 2+4+7+11+12 = 36 (declarer)
        3: ["9C", "5H", "KD", "10S", "3H"],  # Meena: 9+5+13+10+3 = 40
    })
    players[0]["username"] = "Vijay"
    players[1]["username"] = "Ravi"
    players[2]["username"] = "Meena"

    scores = calculate_round_scores(players, declared_by_id=2, joker_rank="6")

    assert scores[1] == 17   # Vijay
    assert scores[2] == 80   # Ravi gets penalty (Vijay is lower)
    assert scores[3] == 40   # Meena


def test_apply_round_scores():
    """apply_round_scores should append scores and update totals."""
    game = {
        "round_current": 1,
        "players": [
            {"user_id": 1, "username": "A", "hand": [], "round_scores": [10], "total_score": 10},
            {"user_id": 2, "username": "B", "hand": [], "round_scores": [20], "total_score": 20},
        ],
    }
    round_scores = {1: 5, 2: 80}
    apply_round_scores(game, round_scores)

    assert game["players"][0]["round_scores"] == [10, 5]
    assert game["players"][0]["total_score"] == 15
    assert game["players"][1]["round_scores"] == [20, 80]
    assert game["players"][1]["total_score"] == 100


def test_build_leaderboard():
    """build_leaderboard should return a string with players sorted by total."""
    game = {
        "players": [
            {"user_id": 1, "username": "Alice", "hand": [], "round_scores": [10, 5], "total_score": 15},
            {"user_id": 2, "username": "Bob", "hand": [], "round_scores": [80, 20], "total_score": 100},
            {"user_id": 3, "username": "Charlie", "hand": [], "round_scores": [0, 40], "total_score": 40},
        ],
    }
    leaderboard = build_leaderboard(game)

    assert "Alice" in leaderboard
    assert "Bob" in leaderboard
    assert "Charlie" in leaderboard
    assert leaderboard.index("Alice") < leaderboard.index("Charlie")
    assert leaderboard.index("Charlie") < leaderboard.index("Bob")
