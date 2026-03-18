"""Shared Telegram error handler."""

from __future__ import annotations

import logging
import traceback
from typing import Any

from telegram import Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TelegramError, TimedOut
from telegram.ext import ContextTypes

from bot.keyboards.main_menu import MAIN_MENU

log = logging.getLogger(__name__)


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
			await update.effective_message.reply_text("⚠️ Couldn't send that response. Try rephrasing your request.")
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