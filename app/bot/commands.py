"""
commands.py — All Telegram command handlers for the 5 Cards bot.

Each function handles one /command. All are async
(python-telegram-bot v20.7 pattern).
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.core import game_engine
from app.services import state_manager
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import send_dm, is_group_admin, get_group_link
from app.bot.timer import start_turn_timer, cancel_turn_timer
from app.config.settings import DEFAULT_ROUNDS, MAX_ROUNDS
from app.core.exceptions import GameException

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /newgame [rounds] — Create a new game lobby."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    if not await is_group_admin(context.bot, chat_id, user.id):
        await update.message.reply_text("🚫 Only group admins can start a new game.")
        return

    if state_manager.game_exists(chat_id):
        existing = state_manager.get_game(chat_id)
        if existing and existing["status"] != "ended":
            await update.message.reply_text("❌ A game is already running in this group. Use /endgame to stop it.")
            return

    rounds = DEFAULT_ROUNDS
    if context.args:
        try:
            rounds = int(context.args[0])
            rounds = max(1, min(rounds, MAX_ROUNDS))
        except ValueError:
            await update.message.reply_text(f"❌ Invalid round count. Use a number 1-{MAX_ROUNDS}.")
            return

    username = user.first_name or user.username or f"Player_{user.id}"
    game = game_engine.create_new_game(chat_id, user.id, username, rounds)
    state_manager.create_game(chat_id, game)

    msg = fmt.fmt_game_created(username, rounds)
    await update.message.reply_text(msg)
    logger.info("/newgame by %s in chat %d (%d rounds)", username, chat_id, rounds)


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join — Join the game lobby."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        username = user.first_name or user.username or f"Player_{user.id}"
        game_engine.add_player(game, user.id, username)
        state_manager.update_game(chat_id, game)

        msg = fmt.fmt_player_joined(username, len(game["players"]))
        await update.message.reply_text(msg)
        logger.info("/join by %s in chat %d", username, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_startgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /startgame — Start the game (admin only). Deals cards."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)

        is_admin = await is_group_admin(context.bot, chat_id, user.id)
        if not is_admin:
            await update.message.reply_text("🚫 Only group admins can start the game.")
            return
        if game["status"] != "waiting":
            await update.message.reply_text("❌ Game has already started!")
            return
        if len(game["players"]) < 2:
            await update.message.reply_text("❌ Need at least 2 players to start. Current: " + str(len(game["players"])))
            return

        game_engine.deal_initial_cards(game)
        state_manager.update_game(chat_id, game)

        group_link = await get_group_link(context.bot, chat_id)
        for player in game["players"]:
            uid = player["user_id"]
            hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
            await send_dm(
                context.bot, uid, hand_msg,
                username=player["username"], chat_id=chat_id,
                reply_markup=keyboards.dm_keyboard(group_link),
            )

        start_msg = fmt.fmt_game_starting(game, 60)
        msg = await update.message.reply_text(start_msg, reply_markup=keyboards.turn_keyboard(game))
        
        start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=True)
        logger.info("/startgame in chat %d — %d players", chat_id, len(game["players"]))
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pick — Pick the top card from the discard pile."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        picked_card = game_engine.process_pick(game, user.id)
        state_manager.update_game(chat_id, game)

        player = state_manager.get_player(game, user.id)
        username = player["username"] if player else "Unknown"

        await update.message.reply_text(
            fmt.fmt_player_picked(username),
        )

        # Send hand via DM
        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        await send_dm(
            context.bot, user.id, hand_msg,
            username=username, chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )

        turn_msg = fmt.fmt_turn_announcement(game, 60)
        msg = await update.message.reply_text(turn_msg, reply_markup=keyboards.turn_keyboard(game))
        start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=False)
        logger.info("/pick by %s in chat %d", username, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /draw — Draw a card from the draw pile."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        if not game["deck"]:
            await update.message.reply_text(fmt.fmt_reshuffle_notice())

        drawn_card = game_engine.process_draw(game, user.id)
        state_manager.update_game(chat_id, game)

        player = state_manager.get_player(game, user.id)
        username = player["username"] if player else "Unknown"

        await update.message.reply_text(
            fmt.fmt_player_drew(username),
        )

        # Send hand via DM
        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        await send_dm(
            context.bot, user.id, hand_msg,
            username=username, chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )
        
        turn_msg = fmt.fmt_turn_announcement(game, 60)
        msg = await update.message.reply_text(turn_msg, reply_markup=keyboards.turn_keyboard(game))
        start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=False)
        logger.info("/draw by %s in chat %d", username, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


def normalize_card(token: str) -> str:
    """Convert shorthand card string like '2c' into actual card format '2C'."""
    token = token.strip().lower()
    rank_map = {
        '2':'2','3':'3','4':'4','5':'5','6':'6',
        '7':'7','8':'8','9':'9','10':'10',
        'j':'J','q':'Q','k':'K','a':'A'
    }
    suit_map = {
        'c':'C','s':'S','h':'H','d':'D'
    }
    if not token:
        return token
    if token.startswith('jk'):
        return token.upper()
    if len(token) < 2:
        return token.upper()
        
    rank = token[:-1]
    suit = token[-1]
    norm_rank = rank_map.get(rank, rank.upper())
    norm_suit = suit_map.get(suit, suit.upper())
    return f"{norm_rank}{norm_suit}"


async def intercept_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Robustly catch /drop commands inside normal text messages (like bot mentions)."""
    if not update.effective_message or not update.effective_message.text:
        return
    text = update.effective_message.text.lower()
    
    if "/drop" not in text:
        return
        
    await cmd_drop(update, context)


async def cmd_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /drop <card1> [card2] ... — Discard card(s)."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        
        args = context.args or []
        if not args and update.message and update.message.text:
            text = update.message.text
            lower_text = text.lower()
            if "/drop" in lower_text:
                drop_idx = lower_text.index("/drop")
                after_drop = text[drop_idx + len("/drop"):].strip()
                if after_drop:
                    args = after_drop.split()

        if not args:
            await update.message.reply_text("❌ Usage: /drop <card> [card2] ...\nExample: /drop 6H  or  /drop 6H 6D 6C")
            return

        try:
            cards_to_drop = [normalize_card(c) for c in args]
        except Exception:
            await update.message.reply_text("⚠️ Invalid card format. Use rank+suit e.g. 2c, Kh, As")
            return
        
        # Validation debug logs
        logger.debug(f"[DROP] User {user.id} attempting to drop: {cards_to_drop}")
        logger.debug(f"[DROP] Current phase: {game['turn_phase']}")
        active_player = game['players'][game['current_turn_idx']]
        logger.debug(f"[DROP] Active player ID: {active_player['user_id']}, Request user ID: {user.id}")
        
        hand_empty = game_engine.process_drop(game, user.id, cards_to_drop)
        logger.debug(f"[DROP] Drop successful! Hand empty: {hand_empty}")
        
        state_manager.update_game(chat_id, game)

        player = state_manager.get_player(game, user.id)
        username = player["username"] if player else "Unknown"

        drop_msg = fmt.fmt_player_dropped(username, cards_to_drop, len(player["hand"]))
        await update.message.reply_text(drop_msg)
        if hand_empty:
            await update.message.reply_text(fmt.fmt_player_hand_empty(username))

        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        await send_dm(
            context.bot, user.id, hand_msg,
            username=username, chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )

        turn_msg = fmt.fmt_turn_announcement(game, 60)
        msg = await update.message.reply_text(turn_msg, reply_markup=keyboards.turn_keyboard(game))
        
        start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=False)
        logger.info("/drop %s by %s in chat %d", cards_to_drop, username, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_declare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /declare — Declare and trigger end-of-round scoring."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        declarer = state_manager.get_player(game, user.id)
        declarer_name = declarer["username"] if declarer else "Unknown"

        round_scores = game_engine.process_declare(game, user.id)
        state_manager.update_game(chat_id, game)
        cancel_turn_timer(context, chat_id)

        await update.message.reply_text(fmt.fmt_declaration(declarer_name))
        await update.message.reply_text(fmt.fmt_all_hands_revealed(game))

        result_msg = fmt.fmt_round_result(game, round_scores, declarer_name)
        is_last = game_engine.is_game_over(game)
        await update.message.reply_text(result_msg, reply_markup=keyboards.next_round_keyboard(is_last))
        logger.info("/declare by %s in chat %d", declarer_name, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_hand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /hand — Send the player's current hand via DM."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        player = state_manager.get_player_or_raise(game, user.id)

        hand_msg = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id)
        sent = await send_dm(
            context.bot, user.id, hand_msg,
            username=player["username"], chat_id=chat_id,
            reply_markup=keyboards.dm_keyboard(group_link),
        )
        if sent:
            await update.message.reply_text("📬 Hand sent to your DM!")
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_scores(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /scores — Show current leaderboard."""
    chat_id = update.effective_chat.id
    if not state_manager.game_exists(chat_id):
        await update.message.reply_text("❌ No game is running here.")
        return

    game = state_manager.get_game(chat_id)
    await update.message.reply_text(fmt.fmt_scores(game))


async def cmd_debugstate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /debugstate — Print internal game state for debugging."""
    chat_id = update.effective_chat.id
    try:
        if not state_manager.game_exists(chat_id):
            await update.message.reply_text("❌ No game is running in this chat.")
            return
            
        game = state_manager.get_game(chat_id)
        
        lines = [
            "🛠 **INTERNAL GAME STATE DEBUG**",
            f"Status: {game['status']}",
            f"Round: {game['round_current']} / {game['rounds_total']}",
            f"Phase: {game['turn_phase']}",
            f"Current Turn Idx: {game['current_turn_idx']}",
            f"Open Card: {game['discard_pile'][-1] if game['discard_pile'] else 'None'}",
            f"Joker Rank: {game['joker_rank']}",
            f"Deck Size: {len(game['deck'])}",
            f"Discard Pile Size: {len(game['discard_pile'])}",
            "--- Players ---"
        ]
        
        for idx, p in enumerate(game['players']):
            indicator = "▶️ " if idx == game['current_turn_idx'] else "   "
            lines.append(f"{indicator}{p['username']} (ID: {p['user_id']}) — Hand: {p['hand']}")
            
        await update.message.reply_text("\n".join(lines))
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_endgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /endgame — Force-end the game (admin only)."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        is_admin = await is_group_admin(context.bot, chat_id, user.id)
        if not is_admin:
            await update.message.reply_text("🚫 Only group admins can end the game.")
            return

        leaderboard = game_engine.end_game(game)
        state_manager.delete_game(chat_id)
        cancel_turn_timer(context, chat_id)
        await update.message.reply_text(leaderboard)
        logger.info("/endgame by admin in chat %d", chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — Show command list and rules summary."""
    await update.message.reply_text(
        "🃏 *Five Cards — Help*\n\n"
        "*Commands:*\n"
        "/newgame — Create a new game lobby (Admin only)\n"
        "/startgame — Start the game (Admin only)\n"
        "/endgame — End current game (Admin only)\n"
        "/join — Join the game lobby\n"
        "/drop [cards] — Drop cards from your hand\n"
        "   Example: /drop 2c Kh As\n"
        "/declare — Declare if you have lowest points\n\n"
        "*Card Format:*\n"
        "Rank + Suit: 2c=2♣ 3h=3♥ Kd=K♦ As=A♠\n\n"
        "*Turn Order:*\n"
        "1️⃣ Drop a card first\n"
        "2️⃣ If Direct Drop → turn ends immediately\n"
        "3️⃣ If Normal Drop → Pick Open Card or Draw\n"
        "⏱ 60 seconds per turn or auto-play triggers",
        parse_mode='Markdown'
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — Welcome message when user starts the bot in DM."""
    await update.message.reply_text(
        "🃏 Welcome to 5 Cards!\n\n"
        "Add me to a group and use /newgame to start playing.\n"
        "Use /help for commands and rules."
    )


# ══════════════════════════════════════════════════════════════════
# FALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unrecognized commands with a help hint."""
    if update.message and update.message.text and update.message.text.startswith("/"):
        await update.message.reply_text("❓ Unknown command. Try /help for a list of commands.")
