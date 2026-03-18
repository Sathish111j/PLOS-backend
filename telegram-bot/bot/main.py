"""Bot entry point — streamlined for the current codebase."""

# pyright: reportMissingImports=false

from __future__ import annotations

import asyncio
import logging
import os
import traceback
import warnings
from typing import Any

from telegram import Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, PicklePersistence, filters
from telegram.warnings import PTBUserWarning

from bot import session
from bot.config import TELEGRAM_BOT_TOKEN, WEBHOOK_PORT, WEBHOOK_SECRET, WEBHOOK_URL
from bot.handlers.auth import build_auth_conversation, cmd_logout
from bot.handlers.ingest import build_ingest_handler
from bot.handlers.chat import build_chat_handler
from bot.handlers.search import build_search_handler
from bot.handlers.buckets import build_buckets_handler
from bot.handlers.jobs import build_jobs_handler
from bot.handlers.suggestions import build_suggestions_handler
from bot.handlers.settings import build_settings_handler
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD

logging.basicConfig(
	format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
	level=logging.INFO,
)
warnings.filterwarnings("ignore", category=PTBUserWarning)
log = logging.getLogger(__name__)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if update.effective_message is None:
		return
	await update.effective_message.reply_text(
		"Use the menu to access the backend services.",
		reply_markup=MAIN_MENU,
	)


async def global_error_handler(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
	err = context.error

	if isinstance(err, RetryAfter):
		log.warning("Telegram rate limit hit — retry after %ss", err.retry_after)
		if isinstance(update, Update) and update.effective_message:
			await update.effective_message.reply_text(
				f"⏳ Telegram is rate-limiting this bot. Please try again in {err.retry_after} seconds."
			)
		return

	if isinstance(err, (TimedOut, NetworkError)):
		log.warning("Network error: %s", err)
		if isinstance(update, Update) and update.effective_message:
			await update.effective_message.reply_text("🌐 Network hiccup — please try again in a moment.")
		return

	if isinstance(err, Forbidden):
		log.warning("Bot blocked or forbidden: %s", err)
		return

	if isinstance(err, BadRequest):
		log.warning("Bad request to Telegram: %s", err)
		if isinstance(update, Update) and update.effective_message:
			await update.effective_message.reply_text(
				"⚠️ Couldn't send that response. Try rephrasing your request."
			)
		return

	if isinstance(err, TelegramError):
		log.error("TelegramError: %s", err)
		if isinstance(update, Update) and update.effective_message:
			await update.effective_message.reply_text("⚠️ A Telegram error occurred. Please try again.")
		return

	log.error(
		"Unhandled exception for update %s:\n%s",
		update,
		"".join(traceback.format_exception(type(err), err, err.__traceback__)),
	)
	if isinstance(update, Update) and update.effective_message:
		await update.effective_message.reply_text(
			"💥 An unexpected error occurred. The issue has been logged.",
			reply_markup=MAIN_MENU,
		)


async def text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if update.effective_message is None or update.effective_user is None:
		return
	if await session.is_authenticated(update.effective_user.id):
		await update.effective_message.reply_text(
			"Use the menu below to continue.",
			reply_markup=MAIN_MENU,
		)
		return
	await update.effective_message.reply_text(
		"Use /start to begin.",
		reply_markup=MAIN_MENU,
	)


async def post_init(application: Application) -> None:
	await session.init()
	log.info("Bot started. Username: %s", application.bot.username)


async def post_shutdown(application: Application) -> None:
	await session.close()
	log.info("Bot shut down cleanly.")


def build_app() -> Application:
	persistence = PicklePersistence(filepath="data/bot_persistence.pkl")

	app = (
		Application.builder()
		.token(TELEGRAM_BOT_TOKEN)
		.persistence(persistence)
		.post_init(post_init)
		.post_shutdown(post_shutdown)
		.build()
	)

	app.add_error_handler(global_error_handler)
	app.add_handler(build_auth_conversation())
	app.add_handler(CommandHandler("logout", cmd_logout))
	app.add_handler(CommandHandler("help", help_command))
	app.add_handler(build_chat_handler())
	app.add_handler(build_search_handler())
	app.add_handler(build_buckets_handler())
	app.add_handler(build_jobs_handler())
	app.add_handler(build_suggestions_handler())
	app.add_handler(build_settings_handler())
	for handler in build_ingest_handler():
		app.add_handler(handler)
	app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_fallback))
	return app


def main() -> None:
	os.makedirs("data", exist_ok=True)
	app = build_app()

	if WEBHOOK_URL:
		log.info("Starting webhook on port %d", WEBHOOK_PORT)
		app.run_webhook(
			listen="0.0.0.0",
			port=WEBHOOK_PORT,
			secret_token=WEBHOOK_SECRET or None,
			webhook_url=f"{WEBHOOK_URL}/bot",
			allowed_updates=Update.ALL_TYPES,
		)
	else:
		log.info("Starting long-polling (dev mode)")
		app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
	main()
