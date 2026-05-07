"""
message_formatter.py — All bot message and text formatting helpers.

Builds user-facing message strings for group chat and DM.
No Telegram API calls — just string construction.
"""

import logging

from app.core.card_utils import format_card, format_hand, hand_value, get_card_rank, get_card_suit
from app.config.settings import DECLARATION_PENALTY

logger = logging.getLogger(__name__)

_SUIT_EMOJI: dict[str, str] = {'H': '♥️', 'D': '♦️', 'C': '♣️', 'S': '♠️'}


def _fmt_open_card(card: str) -> str:
    """Format the open (top of discard pile) card with suit emoji."""
    if not card or card == '—':
        return '—'
    rank = get_card_rank(card)
    suit = get_card_suit(card)
    emoji = _SUIT_EMOJI.get(suit.upper(), suit)
    return f"{rank} {emoji}"


def fmt_game_created(admin_username: str, rounds: int, chat_title: str = "") -> str:
    """Format the 'new game created' announcement for group chat."""
    lines = [
        "╔═══════════════════════════╗",
        "║   🃏  5 CARDS — New Game!  🃏   ║",
        "╚═══════════════════════════╝",
        "",
        f"  👑 Admin: {admin_username}",
        f"  🔁 Rounds: {rounds}",
        "",
        "  📢 Type /join to enter the game!",
        f"  👥 Need at least 2 players (max 10).",
        "",
        "  ⚠️ Before starting, DM me (@bot) so I can",
        "     send you your cards privately!",
    ]
    return "\n".join(lines)


def fmt_player_joined(username: str, player_count: int) -> str:
    """Format the 'player joined' message for group chat."""
    return f"✅ {username} joined! ({player_count} players)"


def fmt_game_starting(game: dict, time_left: int = 60) -> str:
    """Format the 'game starting' announcement shown after deal."""
    open_card = game["discard_pile"][-1] if game["discard_pile"] else "?"
    joker_rank = game["joker_rank"]
    first_player = game["players"][0]

    lines = [
        "╔═══════════════════════════╗",
        f"║   🎯 Round {game['round_current']} / {game['rounds_total']}   🎯          ║",
        "╚═══════════════════════════╝",
        "",
        f"  🃏 Open Card:  {format_card(open_card)}",
        f"  🎭 Joker Rank: {joker_rank}  (All {joker_rank}s = 0 pts)",
        "",
        "  👥 Player Cards:",
        f"  {fmt_card_counts(game)}",
        "",
        f"  ▶️ {first_player['username']}'s turn! (⏳ {time_left}s)",
        "",
        "  📬 Check your DM for your cards!",
    ]
    return "\n".join(lines)


def fmt_turn_announcement(game: dict, time_left: int = 60) -> str:
    """Format the persistent turn announcement shown in group chat.

    This text is used as the body of the single persistent keyboard message
    that is EDITED (not re-sent) on every turn change.
    """
    active = game["players"][game["current_turn_idx"]]
    open_card = game["discard_pile"][-1] if game["discard_pile"] else "—"
    open_display = _fmt_open_card(open_card)
    joker_rank = game["joker_rank"]
    round_no = game["round_current"]
    total_rounds = game["rounds_total"]

    player_lines = "\n".join(
        f"  👤 {p['username']:<12} {'🎴' * min(len(p['hand']), 5)}{'…' if len(p['hand']) > 5 else ''}  ({len(p['hand'])}🃏)"
        for p in game["players"]
    )

    last_action = game.get("last_action", "Game started!")
    
    # Phase-specific instructions
    phase = game.get("turn_phase", "must_discard")
    if phase == "must_discard":
        instruction = "👉 Drop card(s) from your hand!"
    elif phase == "choose_action":
        instruction = "👉 Take a Card from Deck or Pick Open Card!"
    else:
        instruction = ""

    return (
        f"╔════════════════════════╗\n"
        f"║  🎮  5 CARDS  —  Round {round_no}/{total_rounds}  ║\n"
        f"╚════════════════════════╝\n"
        f"\n"
        f"📤  Open Card  ›  {open_display}\n"
        f"🃏  Joker Rank ›  {joker_rank}  (= 0 pts)\n"
        f"📝  Status     ›  {last_action}\n"
        f"\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"▶️  {active['username']}'s Turn   ⏱ {time_left}s\n"
        f"   {instruction}\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"\n"
        f"👥 Players & Scores:\n{player_lines}"
    )


def fmt_discard_prompt(username: str) -> str:
    """Format the discard prompt shown in group after pick/draw."""
    lines = [
        f"📝 {username}, drop a card now!",
        "",
        "  Type: /drop <card>",
        "  Example: /drop 6H",
        "  Multi-drop (same rank): /drop 6H 6D 6C",
    ]
    return "\n".join(lines)


def fmt_hand_dm(player: dict, joker_rank: str) -> str:
    """Format the private hand message sent via DM."""
    from app.core.card_utils import hand_value
    hand = player["hand"]
    formatted = format_hand(hand, joker_rank)
    pts = hand_value(hand, joker_rank)
    
    lines = [
        "┌─────────────────────────┐",
        f"│  🎴 Your Hand ({len(hand)} cards)",
        "└─────────────────────────┘",
        "",
        f"  {formatted}",
        "",
        f"  📊 Total Points: {pts}",
        f"  🎭 Joker rank  : {joker_rank}",
    ]
    return "\n".join(lines)


def fmt_must_discard_dm(player: dict, picked_card: str, joker_rank: str) -> str:
    """Format the 'must discard' reminder sent via DM after pick/draw."""
    lines = [
        f"📥 You picked: {format_card(picked_card)}",
        "",
        "┌─────────────────────────┐",
        f"│  🎴 Your Hand ({len(player['hand'])} cards)",
        "└─────────────────────────┘",
        f"  {format_hand(player['hand'], joker_rank)}",
        "",
        "👉 Go back to group & drop by rank:",
        "   /drop 9        → drop one 9 (any suit)",
        "   /drop 9 9      → drop two 9s",
        "   /drop K K K    → drop three Kings",
    ]
    return "\n".join(lines)


def fmt_player_picked(username: str) -> str:
    """Format the 'player picked open card' group message."""
    return f"📤 {username} picked the open card."


def fmt_player_drew(username: str) -> str:
    """Format the 'player drew from pile' group message."""
    return f"🎴 {username} drew from the pile."


def fmt_player_dropped(username: str, cards_dropped: list[str], cards_remaining: int) -> str:
    """Format the 'player dropped card(s)' group message."""
    if len(cards_dropped) > 1:
        formatted = ", ".join(format_card(c) for c in cards_dropped)
        return (
            f"🔥 {username} dropped {len(cards_dropped)} cards ({formatted})! "
            f"{cards_remaining} cards remaining."
        )
    else:
        return (
            f"🔽 {username} dropped {format_card(cards_dropped[0])}. "
            f"{cards_remaining} cards remaining."
        )


def fmt_group_drop(username: str, cards_dropped: list[str], cards_remaining: int) -> str:
    """Format the group-drop announcement."""
    rank = get_card_rank(cards_dropped[0])
    formatted = ", ".join(format_card(c) for c in cards_dropped)
    return (
        f"💥 {username} group-dropped {len(cards_dropped)} cards of rank {rank}! "
        f"({formatted}) — {cards_remaining} cards remaining."
    )


def fmt_player_hand_empty(username: str) -> str:
    """Format the announcement when a player's hand becomes empty."""
    return f"🌟 {username}'s hand is empty — guaranteed 0 points this round!"


def fmt_declaration(declarer_username: str) -> str:
    """Format the declaration announcement for group chat."""
    lines = [
        "╔═══════════════════════════╗",
        f"║  🏳️ {declarer_username} DECLARES! 🏳️",
        "╚═══════════════════════════╝",
        "",
        "All hands revealed! Calculating scores...",
    ]
    return "\n".join(lines)


def fmt_all_hands_revealed(game: dict) -> str:
    """Format revealed hands of all players after declaration."""
    joker_rank = game["joker_rank"]
    lines: list[str] = [
        "┌─────────────────────────┐",
        "│  📋 Revealed Hands",
        "└─────────────────────────┘",
        "",
    ]

    for player in game["players"]:
        if not player["hand"]:
            lines.append(f"  👤 {player['username']}: 🫗 Empty hand → 0 pts")
        else:
            formatted = format_hand(player["hand"], joker_rank)
            lines.append(f"  👤 {player['username']}: {formatted}")

    return "\n".join(lines)


def fmt_round_result(game: dict, round_scores: dict[int, int], declarer_username: str) -> str:
    """Format the full round result announcement for group chat."""
    round_num = game["round_current"]
    lines = [
        "╔═══════════════════════════╗",
        f"║   📊 Round {round_num} Results",
        "╚═══════════════════════════╝",
    ]

    sorted_players = sorted(
        game["players"], key=lambda p: round_scores.get(p["user_id"], 0),
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
        declared_tag = " 📣" if uid == game.get("declared_by_id") else ""
        lines.append(
            f"  {player['username']}{declared_tag}: "
            f"{pts} pts{indicator}  (Total: {total})"
        )

    lines.append("─────────────────────────")
    if game["round_current"] < game["rounds_total"]:
        lines.append(f"\n🔄 Next round: {game['round_current'] + 1} / {game['rounds_total']}")
    else:
        lines.append("\n🏁 Final round complete! Game over!")
    return "\n".join(lines)


def fmt_card_counts(game: dict) -> str:
    """Format card counts for all players using card-back emoji."""
    parts: list[str] = []
    for player in game["players"]:
        count = len(player["hand"])
        parts.append(f"{player['username']}: {count}🎴")
    return " │ ".join(parts)


def fmt_scores(game: dict) -> str:
    """Format current running scores for /scores command."""
    lines = [
        "╔═══════════════════════════╗",
        "║   📊 Current Scores",
        "╚═══════════════════════════╝",
    ]
    sorted_players = sorted(game["players"], key=lambda p: p["total_score"])
    for player in sorted_players:
        round_details = " + ".join(str(int(s)) for s in player["round_scores"])
        if not round_details:
            round_details = "—"
        lines.append(
            f"  {player['username']}: {int(player['total_score'])} pts"
            f"  ({round_details})"
        )
    lines.append("─────────────────────────")
    return "\n".join(lines)


def fmt_reshuffle_notice() -> str:
    """Format the auto-reshuffle notification for group chat."""
    return "🔄 Draw pile empty — reshuffling discard pile!"


def fmt_help() -> str:
    """Format the /help command response (plain text, no parse_mode needed)."""
    lines = [
        "╔═══════════════════════════╗",
        "║  🃏  5 CARDS — Help & Rules  🃏",
        "╚═══════════════════════════╝",
        "",
        "📋 COMMANDS:",
        "  /newgame [rounds] — Create a new game (default 3 rounds)",
        "  /join — Join the game lobby",
        "  /startgame — Start the game (admin only)",
        "  /pick — Pick the open (top discard) card",
        "  /draw — Draw from the middle pile",
        "  /drop [rank] [rank] — Discard by rank (suit ignored)",
        "    e.g. /drop 9  /drop 9 9  /drop K K K",
        "  /declare — Declare (attempt to win the round)",
        "  /hand — View your hand (sent via DM)",
        "  /scores — View current scores",
        "  /endgame — End the game (admin only)",
        "  /help — Show this help message",
        "",
        "🔄 TURN FLOW:",
        "  1. Drop a card first (start of turn)",
        "  2. Direct Drop (same rank as open card) → turn ends",
        "  3. Normal Drop → then Pick open card OR Draw from pile",
        "  4. OR Declare at the start of your turn",
        "",
        "🎯 SCORING:",
        "  A=1, 2-10=face value, J=11, Q=12, K=13",
        "  Jokers & joker-rank cards = 0 pts",
        "  Lowest total score wins!",
        "",
        "🏳️ DECLARATION:",
        "  • Your score < everyone → You get 0 pts!",
        "  • Someone has lower → You get 80 pts penalty",
        "  • Someone ties → Both get 0 (unless penalty applies)",
        "  • Empty hand → Always 0 pts",
    ]
    return "\n".join(lines)


def fmt_dm_warning(username: str, bot_username: str) -> str:
    """Format the DM prerequisite warning."""
    return (
        f"⚠️ @{username} — please start a DM with me first! "
        f"Click @{bot_username} and press START."
    )


def format_hand_for_display(hand: list[str], joker_rank: str = "") -> str:
    """Format a player's hand as emoji card list for DM display.

    Used by the action:hand button to show cards with suit emojis
    and a total point value line.

    Args:
        hand:       List of card strings.
        joker_rank: Current round's joker rank (for point calc).

    Returns:
        Multi-line string with one card per line and a total.
    """
    if not hand:
        return "🫗 Your hand is empty!"

    lines: list[str] = []
    total = 0
    for card in hand:
        rank = get_card_rank(card)
        suit = get_card_suit(card)
        emoji = _SUIT_EMOJI.get(suit.upper(), suit)
        pts = int(hand_value([card], joker_rank)) if joker_rank else 0
        lines.append(f"  {rank} {emoji}  → {pts} pts")
        total += pts
    lines.append(f"\n📊 Total: {int(total)} pts")
    return "\n".join(lines)
