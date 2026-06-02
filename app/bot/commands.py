"""
commands.py — All Telegram command handlers for the 5 Cards bot.

Each function handles one /command. All are async
(python-telegram-bot v20.7 pattern).
"""

import html
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.core import game_engine
from app.services import state_manager
from app.services import message_formatter as fmt
from app.bot import keyboards
from app.bot.helpers import send_dm, is_group_admin, get_group_link, send_new_turn_message
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
    game = game_engine.create_new_game(chat_id, user.id, username, rounds, tg_username=user.username)
    state_manager.create_game(chat_id, game)

    msg = fmt.fmt_game_created(username, rounds)
    await update.message.reply_text(msg, parse_mode="HTML")
    logger.info("/newgame by %s in chat %d (%d rounds)", username, chat_id, rounds)


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /join — Join the game lobby."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        username = user.first_name or user.username or f"Player_{user.id}"
        game_engine.add_player(game, user.id, username, tg_username=user.username)
        state_manager.update_game(chat_id, game)

        msg = fmt.fmt_player_joined(username, len(game["players"]))
        await update.message.reply_text(msg, parse_mode="HTML")
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
        if game["admin_id"] != user.id and not is_admin:
            await update.message.reply_text("🚫 Only the game creator or group admins can start the game.")
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
            msg_id = await send_dm(
                context.bot, uid, hand_msg,
                username=player["username"], chat_id=chat_id,
                reply_markup=keyboards.dm_keyboard(group_link),
            )
            if msg_id:
                player["dm_message_id"] = msg_id

        # CHANGE #1: Send the ONE persistent keyboard message and store its ID
        start_msg = fmt.fmt_turn_announcement(game, 60)
        bot_info = await context.bot.get_me()
        msg = await update.message.reply_text(
            start_msg,
            reply_markup=keyboards.persistent_game_keyboard(bot_info.username),
            parse_mode="HTML"
        )

        # Store keyboard_message_id in game state so all callers can edit it
        game["keyboard_message_id"] = msg.message_id
        state_manager.update_game(chat_id, game)

        await start_turn_timer(context, chat_id, game, message_id=msg.message_id, is_startgame=False)
        logger.info("/startgame in chat %d — %d players, keyboard_msg=%d", chat_id, len(game["players"]), msg.message_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /kick — Remove a player from the game (admin only)."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        is_admin = await is_group_admin(context.bot, chat_id, user.id)
        if game["admin_id"] != user.id and not is_admin:
            await update.message.reply_text("🚫 Only the game creator or group admins can kick players.")
            return

        target_user_id = None
        target_name = ""

        # Check if replying to a message
        if update.message.reply_to_message:
            target_user_id = update.message.reply_to_message.from_user.id
            target_name = update.message.reply_to_message.from_user.first_name
        elif context.args:
            # Try to match by username or name
            query = " ".join(context.args).lower().replace("@", "")
            for p in game["players"]:
                if (p.get("tg_username") and p["tg_username"].lower() == query) or \
                   (p["username"].lower() == query):
                    target_user_id = p["user_id"]
                    target_name = p["username"]
                    break

        if not target_user_id:
            await update.message.reply_text("❌ Specify a player to kick by replying to their message or using /kick @username or /kick Name.")
            return

        if target_user_id == user.id:
            await update.message.reply_text("❌ You cannot kick yourself.")
            return

        game_ended = game_engine.remove_player(game, target_user_id)
        
        await update.message.reply_text(f"🚪 <b>{html.escape(target_name)}</b> has been kicked from the game.", parse_mode="HTML")

        if game_ended:
            leaderboard = game_engine.end_game(game)
            state_manager.delete_game(chat_id)
            await cancel_turn_timer(context, chat_id)
            await update.message.reply_text("🛑 Game ended because less than 2 players remain.\n\n" + leaderboard, parse_mode="HTML")
            return
            
        state_manager.update_game(chat_id, game)

        if game["status"] == "running":
            await cancel_turn_timer(context, chat_id)
            await send_new_turn_message(context, chat_id, game, edit_only=False)
            await start_turn_timer(context, chat_id, game)

        logger.info("/kick on %s by %s in chat %d", target_name, user.username, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pick — Pick the top card from the discard pile."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        game_engine.process_pick(game, user.id)
        state_manager.update_game(chat_id, game)

        from app.bot.helpers import send_new_turn_message, update_hand_dm
        await send_new_turn_message(context, chat_id, game)
        await update_hand_dm(context, chat_id, game, user.id)
        await start_turn_timer(context, chat_id, game)
        logger.info("/pick by %d in chat %d", user.id, chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_draw(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /draw — Draw a card from the draw pile."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        if not game["deck"]:
            await update.message.reply_text(fmt.fmt_reshuffle_notice(), parse_mode="HTML")

        game_engine.process_draw(game, user.id)
        state_manager.update_game(chat_id, game)

        from app.bot.helpers import send_new_turn_message, update_hand_dm
        await send_new_turn_message(context, chat_id, game)
        await update_hand_dm(context, chat_id, game, user.id)
        await start_turn_timer(context, chat_id, game)
        logger.info("/draw by %d in chat %d", user.id, chat_id)
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
    """Robustly catch /drop commands inside normal text messages."""
    if not update.effective_message or not update.effective_message.text:
        return
    text = update.effective_message.text.lower().strip()
    
    # Matches "/drop", "@bot /drop", "drop 9", etc.
    # We look for the word "drop" and check if it's the start or preceded by a bot mention
    tokens = text.split()
    if not tokens:
        return
        
    # Check if first token is 'drop' or '/drop'
    # OR if first token is a mention and second is 'drop' or '/drop'
    is_drop = False
    if tokens[0] in ("drop", "/drop"):
        is_drop = True
    elif len(tokens) > 1 and tokens[0].startswith("@") and tokens[1] in ("drop", "/drop"):
        is_drop = True
        
    if is_drop:
        await cmd_drop(update, context)


async def cmd_drop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /drop [rank] [rank] ... — Discard card(s) by rank."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)

        args = context.args or []
        if not args and update.message and update.message.text:
            text = update.message.text
            lower_text = text.lower()
            if "/drop" in lower_text or "drop" in lower_text:
                keyword = "/drop" if "/drop" in lower_text else "drop"
                drop_idx = lower_text.index(keyword)
                after_drop = text[drop_idx + len(keyword):].strip()
                if after_drop:
                    args = after_drop.split()

        if not args:
            await update.message.reply_text(
                "❌ Usage: /drop [rank]\n"
                "Example: /drop 9  or  /drop K K"
            )
            return

        result = game_engine.process_drop(game, user.id, args)
        state_manager.update_game(chat_id, game)

        from app.bot.helpers import update_hand_dm

        if result["turn_advanced"]:
            # Turn ended (Match or Hand Empty)
            await cancel_turn_timer(context, chat_id)
            await send_new_turn_message(context, chat_id, game, edit_only=False)
            await start_turn_timer(context, chat_id, game)
        else:
            # Turn continues: player must now pick or draw
            await cancel_turn_timer(context, chat_id)
            await send_new_turn_message(context, chat_id, game, edit_only=True)
            await start_turn_timer(context, chat_id, game)
            
            # Also notify in group that they must draw
            player = state_manager.get_player(game, user.id)
            safe_name = html.escape(player['username'])
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ <b>No Match!</b>\n👤 {safe_name}, you must draw a card from the pile or pick the open card to end your turn.",
                parse_mode="HTML",
                reply_markup=keyboards.must_draw_keyboard()
            )

        await update_hand_dm(context, chat_id, game, user.id)

        logger.info("/drop by %d in chat %d", user.id, chat_id)
    except GameException as e:
        await update.message.reply_text(f"⚠️ {e.message}")
    except Exception as e:
        # Senior OG Debugging: Show the actual error so we can fix it!
        error_msg = f"❌ Internal error ({type(e).__name__}): {str(e)}"
        logger.error("Unexpected error in cmd_drop: %s", e, exc_info=True)
        await update.message.reply_text(error_msg)


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
        await cancel_turn_timer(context, chat_id)

        await update.message.reply_text(fmt.fmt_declaration(declarer_name), parse_mode="HTML")
        await update.message.reply_text(fmt.fmt_all_hands_revealed(game), parse_mode="HTML")

        result_msg = fmt.fmt_round_result(game, round_scores, declarer_name)
        is_last = game_engine.is_game_over(game)
        await update.message.reply_text(result_msg, reply_markup=keyboards.next_round_keyboard(is_last), parse_mode="HTML")
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
            player["dm_message_id"] = sent
            state_manager.update_game(chat_id, game)
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
    await update.message.reply_text(fmt.fmt_scores(game), parse_mode="HTML")


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
            
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_endgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /endgame — Force-end the game (admin only)."""
    chat_id = update.effective_chat.id
    user = update.effective_user

    try:
        game = state_manager.get_game_or_raise(chat_id)
        is_admin = await is_group_admin(context.bot, chat_id, user.id)
        if game["admin_id"] != user.id and not is_admin:
            await update.message.reply_text("🚫 Only the game creator or group admins can end the game.")
            return

        leaderboard = game_engine.end_game(game)
        state_manager.delete_game(chat_id)
        await cancel_turn_timer(context, chat_id)
        await update.message.reply_text(leaderboard, parse_mode="HTML")
        logger.info("/endgame by admin in chat %d", chat_id)
    except GameException as e:
        await update.message.reply_text(e.message)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — Show command list and rules summary."""
    await update.message.reply_text(
        "<b>🃏 Five Cards — Help</b>\n\n"
        "<b>Commands:</b>\n"
        "/newgame — Create a new game lobby\n"
        "/startgame — Start the game (Creator/Admin)\n"
        "/endgame — End current game (Creator/Admin)\n"
        "/kick [user] — Kick a player (Creator/Admin)\n"
        "/join — Join the game lobby\n"
        "/drop [rank] — Drop card(s) by rank (e.g. <code>/drop 9</code>)\n"
        "/declare — Declare at the start of your turn\n\n"
        "<b>Turn Order:</b>\n"
        "1️⃣ <b>Drop</b> a card first (start of turn)\n"
        "2️⃣ <b>Match Rank</b> (Direct Drop) → Turn ends immediately!\n"
        "3️⃣ <b>No Match</b> → You must <b>Draw</b> from pile or <b>Pick</b> open card to end turn.\n\n"
        "⏱ 60 seconds per action or auto-play triggers.",
        parse_mode="HTML"
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — Welcome message or deep-link handler."""
    user = update.effective_user
    if context.args and context.args[0] == "hand":
        res = state_manager.find_game_by_user_id(user.id)
        if not res:
            await update.message.reply_text("❌ You are not in any active game.")
            return
        
        chat_id, game = res
        player = state_manager.get_player(game, user.id)
        
        hand_text = fmt.fmt_hand_dm(player, game["joker_rank"])
        group_link = await get_group_link(context.bot, chat_id, message_id=game.get("keyboard_message_id", 1))
        
        msg = await update.message.reply_text(
            hand_text,
            parse_mode="HTML",
            reply_markup=keyboards.dm_keyboard(group_link)
        )
        player["dm_message_id"] = msg.message_id
        state_manager.update_game(chat_id, game)
        return

    await update.message.reply_text(
        "🃏 Welcome to 5 Cards!\n\n"
        "Add me to a group and use /newgame to start playing.\n"
        "Use /help for commands and rules."
    )


# ══════════════════════════════════════════════════════════════════
# FALLBACK HANDLER
# ══════════════════════════════════════════════════════════════════


async def cmd_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries for the /drop rank picker."""
    query = update.inline_query
    if not query:
        return
    
    text = query.query.lower().strip()
    if not text.startswith("/drop"):
        return
        
    user_id = query.from_user.id
    # Find the game where this user is active
    game_data = state_manager.find_game_by_user_id(user_id)
    if not game_data:
        return
        
    chat_id, game = game_data
    player = state_manager.get_player(game, user_id)
    if not player:
        return
        
    # Get unique ranks in hand
    ranks = sorted(list(set(game_engine.get_ranks_in_hand(player["hand"]))))
    
    from telegram import InlineQueryResultArticle, InputTextMessageContent
    import uuid
    
    results = []
    for r in ranks:
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=f"Drop {r}",
                description=f"Drop card(s) of rank {r}",
                input_message_content=InputTextMessageContent(f"/drop {r}")
            )
        )
        
    await query.answer(results, cache_time=1)


