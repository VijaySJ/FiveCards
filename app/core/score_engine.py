"""
score_engine.py — Declaration scoring, round score application, and leaderboard.

Implements the 4 scoring rules from Section 4F exactly:
  RULE 1: Declarer has lowest → declarer gets 0, others get their hand value.
  RULE 2: ANY other player has lower than declarer → declarer gets 80 penalty.
  RULE 3: ANY other player ties with declarer → both get 0 (but RULE 2 overrides if also triggered).
  RULE 4: Player with 0 cards in hand ALWAYS scores 0.

All functions are pure sync — no Telegram imports.
"""

import logging
from app.core.card_utils import hand_value
from app.config.settings import DECLARATION_PENALTY

logger = logging.getLogger(__name__)


def calculate_round_scores(
    players: list[dict], declared_by_id: int, joker_rank: str,
) -> dict[int, int]:
    """Calculate the round score for every player after a declaration.

    Args:
        players: List of player dicts with "user_id", "hand" keys.
        declared_by_id: user_id of the player who declared.
        joker_rank: Current round's joker rank.

    Returns:
        Dict mapping user_id → points scored this round.
    """
    scores: dict[int, int] = {}
    hand_values: dict[int, int] = {}
    for p in players:
        uid = p["user_id"]
        if not p["hand"]:
            hand_values[uid] = 0
        else:
            hand_values[uid] = hand_value(p["hand"], joker_rank)

    declarer_value = hand_values[declared_by_id]
    someone_lower = False
    someone_tied = False

    for p in players:
        uid = p["user_id"]
        if uid == declared_by_id:
            continue
        v = hand_values[uid]
        if v < declarer_value:
            someone_lower = True
        if v == declarer_value:
            someone_tied = True

    if someone_lower:
        logger.info("RULE 2: Declarer %d gets %d penalty", declared_by_id, DECLARATION_PENALTY)
        for p in players:
            uid = p["user_id"]
            if not p["hand"]:
                scores[uid] = 0
            elif uid == declared_by_id:
                scores[uid] = DECLARATION_PENALTY
            elif hand_values[uid] == declarer_value:
                scores[uid] = 0
            else:
                scores[uid] = hand_values[uid]
    elif someone_tied:
        logger.info("RULE 3: Declarer %d and tied opponent(s) get 0", declared_by_id)
        for p in players:
            uid = p["user_id"]
            if not p["hand"]:
                scores[uid] = 0
            elif uid == declared_by_id:
                scores[uid] = 0
            elif hand_values[uid] == declarer_value:
                scores[uid] = 0
            else:
                scores[uid] = hand_values[uid]
    else:
        logger.info("RULE 1: Declarer %d has lowest hand, scores 0", declared_by_id)
        for p in players:
            uid = p["user_id"]
            if not p["hand"]:
                scores[uid] = 0
            elif uid == declared_by_id:
                scores[uid] = 0
            else:
                scores[uid] = hand_values[uid]

    logger.info("Round scores: %s", scores)
    return scores


def apply_round_scores(game: dict, round_scores: dict[int, int]) -> None:
    """Append round scores to each player's history and update totals.

    Args:
        game: The full game state dict.
        round_scores: Dict mapping user_id → points for this round.
    """
    for player in game["players"]:
        uid = player["user_id"]
        pts = int(round_scores.get(uid, 0))
        player["round_scores"].append(pts)
        player["total_score"] = int(player.get("total_score", 0) + pts)
    logger.info(
        "Applied round %d scores. Totals: %s",
        game["round_current"],
        {p["username"]: p["total_score"] for p in game["players"]},
    )


def build_leaderboard(game: dict) -> str:
    """Build a formatted leaderboard string sorted by total_score ascending.

    Args:
        game: The full game state dict.

    Returns:
        Multi-line formatted leaderboard string.
    """
    sorted_players = sorted(game["players"], key=lambda p: p["total_score"])
    lines: list[str] = []
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏆  FINAL LEADERBOARD  🏆")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    for idx, player in enumerate(sorted_players):
        if idx == 0:
            badge = "🥇"
        elif idx == 1:
            badge = "🥈"
        elif idx == 2:
            badge = "🥉"
        elif idx == len(sorted_players) - 1:
            badge = "💀"
        else:
            badge = f"#{idx + 1}"

        rounds_count = len(player["round_scores"])

        lines.append(f"{badge}  {player['username']}:  {int(player['total_score'])} pts")
        lines.append(f"     Rounds: {rounds_count}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def build_round_summary(
    game: dict, round_scores: dict[int, int], round_number: int
) -> str:
    """Build a formatted round result summary.

    Args:
        game: The full game state dict.
        round_scores: Dict mapping user_id → points for this round.
        round_number: Which round just ended.

    Returns:
        Multi-line formatted round summary string.
    """
    lines: list[str] = []
    lines.append(f"📊  Round {round_number} Results")
    lines.append("─────────────────────────")

    sorted_players = sorted(
        game["players"], key=lambda p: round_scores.get(p["user_id"], 0)
    )

    for player in sorted_players:
        uid = player["user_id"]
        pts = int(round_scores.get(uid, 0))
        total = int(player["total_score"])
        indicator = ""
        if pts == DECLARATION_PENALTY:
            indicator = " ⚠️ PENALTY"
        elif pts == 0:
            indicator = " ✨"
        lines.append(f"  {player['username']}: {pts} pts{indicator}  (Total: {total})")

    lines.append("─────────────────────────")
    return "\n".join(lines)
