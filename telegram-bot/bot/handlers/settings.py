"""Settings handler — Sprint 5.

Flow:
  User taps "⚙️ Settings"   → GET /settings → formatted display
  Each setting has an edit  button → ask for new value → PATCH /settings
  User taps "🔙 Back"        → main menu

Settings are displayed as a read-only summary with per-field edit
buttons. PATCH is called with only the changed field so unrelated
settings are never overwritten.

The raw settings object shape will vary by backend. The handler
treats it as a flat key→value dict and formats whatever keys come
back. Known keys get friendly labels; unknown keys are shown as-is.
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD
import bot.api_client as api

log = logging.getLogger(__name__)

SETTINGS_VIEW = 60
SETTINGS_EDIT = 61

LABELS: dict[str, str] = {
	"language": "Language",
	"default_bucket": "Default bucket",
	"auto_ingest": "Auto-ingest",
	"suggestions_enabled": "Suggestions",
	"search_result_limit": "Search results limit",
	"chat_history_limit": "Chat history turns",
	"timezone": "Timezone",
	"notification_email": "Notification email",
	"embedding_model": "Embedding model",
	"chunk_size": "Chunk size",
	"chunk_overlap": "Chunk overlap",
}

READ_ONLY_KEYS = {"embedding_model", "chunk_size", "chunk_overlap"}


async def _jwt(update: Update) -> str | None:
	uid = update.effective_user.id if update.effective_user else None
	if uid is None:
		return None
	jwt = await session.get_jwt(uid)
	if not jwt:
		target = update.effective_message or (update.callback_query.message if update.callback_query else None)
		if target:
			await target.reply_text(
				"Session expired. Tap /start to log in again.",
				reply_markup=WELCOME_KEYBOARD,
			)
	return jwt


def _label(key: str) -> str:
	return LABELS.get(key, key.replace("_", " ").capitalize())


def _fmt_value(v: Any) -> str:
	if isinstance(v, bool):
		return "✅ On" if v else "⬜ Off"
	if v is None or v == "":
		return "—"
	return str(v)


def _fmt_settings(settings: dict) -> str:
	lines = ["⚙️ *Settings*\n"]
	for key, val in settings.items():
		if isinstance(val, (dict, list)):
			continue
		lines.append(f"*{_label(key)}:*  {_fmt_value(val)}")
	return "\n".join(lines)


def _settings_kb(settings: dict) -> InlineKeyboardMarkup:
	rows = []
	editable = [k for k, v in settings.items() if not isinstance(v, (dict, list)) and k not in READ_ONLY_KEYS]
	for key in editable:
		rows.append([InlineKeyboardButton(f"✏️ Edit {_label(key)}", callback_data=f"st:edit:{key}")])
	rows.append([
		InlineKeyboardButton("🔄 Refresh", callback_data="st:reload"),
		InlineKeyboardButton("🔙 Back", callback_data="st:menu"),
	])
	return InlineKeyboardMarkup(rows)


async def _fetch_settings(jwt: str) -> dict:
	return await api.get_settings(jwt)


async def _patch_settings(jwt: str, payload: dict) -> dict:
	return await api.update_settings(jwt, payload)


async def settings_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _jwt(update)
	if not jwt or update.effective_chat is None or update.effective_message is None:
		return ConversationHandler.END

	await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

	try:
		settings = await _fetch_settings(jwt)
	except APIError as exc:
		if exc.status == 401 and update.effective_user is not None:
			await session.delete_jwt(update.effective_user.id)
		await update.effective_message.reply_text(f"Could not load settings: {exc.detail}", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	context.user_data["st_settings"] = settings

	await update.effective_message.reply_text(
		_fmt_settings(settings),
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=_settings_kb(settings),
	)
	return SETTINGS_VIEW


async def settings_callback(update: Update, context: CallbackContext) -> int:
	cq = update.callback_query
	if cq is None or update.effective_user is None or update.effective_chat is None:
		return ConversationHandler.END
	await cq.answer()
	jwt = await session.get_jwt(update.effective_user.id)

	if not jwt:
		await cq.edit_message_text("Session expired. Tap /start to log in again.")
		return ConversationHandler.END

	data = cq.data or ""
	settings = context.user_data.get("st_settings", {})

	if data == "st:menu":
		await cq.edit_message_text("Returning to main menu.")
		await context.bot.send_message(update.effective_chat.id, "What would you like to do?", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	if data == "st:reload":
		await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			settings = await _fetch_settings(jwt)
		except APIError as exc:
			await cq.answer(f"Refresh failed: {exc.detail}", show_alert=True)
			return SETTINGS_VIEW
		context.user_data["st_settings"] = settings
		await cq.edit_message_text(_fmt_settings(settings), parse_mode=ParseMode.MARKDOWN, reply_markup=_settings_kb(settings))
		return SETTINGS_VIEW

	if data.startswith("st:edit:"):
		key = data[len("st:edit:"):]
		if key in READ_ONLY_KEYS:
			await cq.answer("This setting is read-only.", show_alert=True)
			return SETTINGS_VIEW

		current = _fmt_value(settings.get(key))
		context.user_data["st_editing_key"] = key

		await cq.edit_message_text(
			f"✏️ *Edit: {_label(key)}*\n\nCurrent value: `{current}`\n\nSend the new value, or tap Cancel:",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="st:cancel_edit")]]),
		)
		return SETTINGS_EDIT

	if data == "st:cancel_edit":
		context.user_data.pop("st_editing_key", None)
		await cq.edit_message_text(_fmt_settings(settings), parse_mode=ParseMode.MARKDOWN, reply_markup=_settings_kb(settings))
		return SETTINGS_VIEW

	return SETTINGS_VIEW


async def settings_receive_value(update: Update, context: CallbackContext) -> int:
	jwt = await _jwt(update)
	if not jwt or update.effective_message is None or update.effective_user is None:
		return ConversationHandler.END

	key = context.user_data.pop("st_editing_key", None)
	settings = context.user_data.get("st_settings", {})

	if not key:
		await update.effective_message.reply_text("Nothing to edit.", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	raw_value = (update.effective_message.text or "").strip()
	existing = settings.get(key)
	value: Any = raw_value
	if isinstance(existing, bool):
		value = raw_value.lower() in ("true", "yes", "1", "on", "✅")
	elif isinstance(existing, int):
		try:
			value = int(raw_value)
		except ValueError:
			await update.effective_message.reply_text(
				f"Expected an integer for *{_label(key)}*. Try again:",
				parse_mode=ParseMode.MARKDOWN,
				reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="st:cancel_edit")]]),
			)
			context.user_data["st_editing_key"] = key
			return SETTINGS_EDIT
	elif isinstance(existing, float):
		try:
			value = float(raw_value)
		except ValueError:
			await update.effective_message.reply_text(
				f"Expected a number for *{_label(key)}*. Try again:",
				parse_mode=ParseMode.MARKDOWN,
			)
			context.user_data["st_editing_key"] = key
			return SETTINGS_EDIT

	try:
		updated = await _patch_settings(jwt, {key: value})
	except APIError as exc:
		await update.effective_message.reply_text(
			f"Update failed: {exc.detail}",
			reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ Back to settings", callback_data="st:reload")]]),
		)
		return SETTINGS_VIEW

	settings.update(updated if isinstance(updated, dict) else {key: value})
	context.user_data["st_settings"] = settings

	await update.effective_message.reply_text(
		f"✅ *{_label(key)}* updated to `{_fmt_value(value)}`",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ Back to settings", callback_data="st:reload")]]),
	)
	return SETTINGS_VIEW


async def settings_back(update: Update, context: CallbackContext) -> int:
	context.user_data.pop("st_settings", None)
	context.user_data.pop("st_editing_key", None)
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_settings_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")

	return ConversationHandler(
		entry_points=[MessageHandler(filters.Regex(r"^⚙️ Settings$"), settings_entry)],
		states={
			SETTINGS_VIEW: [CallbackQueryHandler(settings_callback, pattern=r"^st:"), MessageHandler(back_filter, settings_back)],
			SETTINGS_EDIT: [
				CallbackQueryHandler(settings_callback, pattern=r"^st:"),
				MessageHandler(back_filter, settings_back),
				MessageHandler(filters.TEXT & ~filters.COMMAND & ~back_filter, settings_receive_value),
			],
		},
		fallbacks=[MessageHandler(back_filter, settings_back)],
		persistent=True,
		name="settings_conversation",
	)