"""
main.py — Application setup and entry point for the 5 Cards Telegram bot.

Builds the Application, registers all handlers, and starts polling.
"""

import logging
import sys

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config.settings import BOT_TOKEN
from app.bot.commands import (
    cmd_start,
    cmd_newgame,
    cmd_join,
    cmd_startgame,
    cmd_pick,
    cmd_draw,
    cmd_drop,
    cmd_declare,
    cmd_hand,
    cmd_scores,
    cmd_debugstate,
    cmd_endgame,
    cmd_help,
    handle_unknown,
)
from app.bot.callbacks import handle_callback

logger = logging.getLogger(__name__)


def main() -> None:
    """Build and run the Telegram bot application.

    Sets up all handlers and starts long-polling.
    """
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set! Create a .env file with BOT_TOKEN=your_token")
        sys.exit(1)

    logger.info("Starting 5 Cards bot...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 1. Raw drop interceptor — MUST be first, but MUST NOT swallow /commands
    from app.bot.commands import intercept_drop
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            intercept_drop
        ),
        group=0
    )

    # 2. Admin commands
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("startgame", cmd_startgame))
    app.add_handler(CommandHandler("endgame", cmd_endgame))

    # 3. Player commands
    app.add_handler(CommandHandler("join", cmd_join))
    app.add_handler(CommandHandler("declare", cmd_declare))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("pick", cmd_pick))
    app.add_handler(CommandHandler("draw", cmd_draw))
    app.add_handler(CommandHandler("drop", cmd_drop))
    app.add_handler(CommandHandler("hand", cmd_hand))
    app.add_handler(CommandHandler("scores", cmd_scores))
    app.add_handler(CommandHandler("debugstate", cmd_debugstate))

    # ── Callback query handler ────────────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Fallback for unknown commands ─────────────────────────────
    app.add_handler(MessageHandler(filters.COMMAND, handle_unknown))

    # ── Start polling ─────────────────────────────────────────────
    logger.info("Bot is running! Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
