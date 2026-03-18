"""Suggestions handler — Sprint 5.

Flow:
  User taps "💡 Suggestions"  → paginated list (GET /suggestions)
  Each suggestion has:
    [✅ Approve]  [❌ Reject]  buttons inline
  User taps Approve           → POST /suggestions/{id}/approve
  User taps Reject            → asks for optional comment → POST /suggestions/{id}/reject
  User taps "📜 History"      → GET /suggestions/history (read-only list)
  User taps "🔙 Back"         → main menu
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import html
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

import bot.api_client as api
from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD

log = logging.getLogger(__name__)

SUGG_LIST = 50
SUGG_HISTORY = 51
SUGG_REJECT = 52

PAGE_SIZE = 5

STATUS_EMOJI = {
	"pending": "🟡",
	"approved": "✅",
	"rejected": "❌",
}


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


def _as_list(payload: Any) -> list[dict]:
	if isinstance(payload, list):
		return payload
	if isinstance(payload, dict):
		for key in ("suggestions", "items", "results", "data"):
			value = payload.get(key)
			if isinstance(value, list):
				return value
	return []


def _total_from(payload: Any, items: list[dict]) -> int:
	if isinstance(payload, dict):
		for key in ("total", "count", "total_count", "total_items"):
			value = payload.get(key)
			if isinstance(value, int):
				return value
	return len(items)


async def _load_pending(jwt: str, page: int) -> tuple[list[dict], int]:
	offset = max(page, 0) * PAGE_SIZE
	payload = await api.get_suggestions(jwt, status="pending", offset=offset, limit=PAGE_SIZE)
	items = _as_list(payload)
	return items, _total_from(payload, items)


async def _load_history(jwt: str, page: int) -> tuple[list[dict], int]:
	offset = max(page, 0) * PAGE_SIZE
	payload = await api.get_suggestion_history(jwt, offset=offset, limit=PAGE_SIZE)
	items = _as_list(payload)
	return items, _total_from(payload, items)


async def _approve(jwt: str, suggestion_id: str) -> dict[str, Any]:
	return await api.approve_suggestion(jwt, suggestion_id)


async def _reject(jwt: str, suggestion_id: str, comment: str = "") -> dict[str, Any]:
	return await api.reject_suggestion(jwt, suggestion_id, comment=comment)


def _short(value: Any, limit: int = 60) -> str:
	text = str(value or "").strip()
	return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _sugg_id(item: dict) -> str:
	return str(item.get("id") or item.get("suggestion_id") or item.get("uuid") or "")


def _sugg_title(item: dict) -> str:
	return _short(item.get("title") or item.get("name") or item.get("description") or "Suggestion", 70)


def _sugg_status(item: dict) -> str:
	return str(item.get("status") or "pending").lower()


def _fmt_pending(items: list[dict], page: int, total: int) -> str:
	pending = sum(1 for s in items if _sugg_status(s) == "pending")
	start = page * PAGE_SIZE + 1 if total else 0
	end = min((page + 1) * PAGE_SIZE, total) if total else len(items)
	lines = [f"💡 <b>Suggestions</b> — {pending} pending on this page"]
	if total:
		lines[0] += f" • {start}-{end} of {total}"
	for index, item in enumerate(items, start=start or 1):
		status = _sugg_status(item)
		emoji = STATUS_EMOJI.get(status, "🟡")
		lines.append(f"\n{index}. {emoji} <b>{html.escape(_sugg_title(item))}</b>")
		detail = item.get("summary") or item.get("text") or item.get("reason") or item.get("comment") or ""
		if detail:
			lines.append(f"   {html.escape(_short(detail, 140))}")
	return "\n".join(lines)


def _fmt_history(items: list[dict], page: int, total: int) -> str:
	if not items:
		return "📜 <b>Suggestion history</b> — no entries."
	start = page * PAGE_SIZE + 1 if total else 1
	end = min((page + 1) * PAGE_SIZE, total) if total else len(items)
	lines = [f"📜 <b>Suggestion history</b> • {start}-{end} of {total or len(items)}"]
	for index, item in enumerate(items, start=start):
		status = _sugg_status(item)
		emoji = STATUS_EMOJI.get(status, "🔵")
		comment = _short(item.get("comment") or item.get("resolution") or "", 100)
		lines.append(f"\n{index}. {emoji} <b>{html.escape(_sugg_title(item))}</b>")
		lines.append(f"   Status: {html.escape(status)}")
		if comment:
			lines.append(f"   Note: {html.escape(comment)}")
	return "\n".join(lines)


def _pending_keyboard(items: list[dict], page: int, total: int) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	for item in items:
		sid = _sugg_id(item)
		title = _sugg_title(item)
		status = _sugg_status(item)
		emoji = STATUS_EMOJI.get(status, "🟡")
		rows.append([InlineKeyboardButton(f"{emoji} {title[:48]}", callback_data="sg:noop")])
		if status == "pending" and sid:
			rows.append([
				InlineKeyboardButton("✅ Approve", callback_data=f"sg:approve:{sid}:{page}"),
				InlineKeyboardButton("❌ Reject", callback_data=f"sg:reject_ask:{sid}:{page}"),
			])

	nav: list[InlineKeyboardButton] = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"sg:list:{page - 1}"))
	if total > (page + 1) * PAGE_SIZE:
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"sg:list:{page + 1}"))
	if nav:
		rows.append(nav)

	rows.append([
		InlineKeyboardButton("📜 History", callback_data="sg:history:0"),
		InlineKeyboardButton("🔄 Refresh", callback_data=f"sg:reload:{page}"),
		InlineKeyboardButton("🔙 Back", callback_data="sg:menu"),
	])
	return InlineKeyboardMarkup(rows)


def _history_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
	rows: list[list[InlineKeyboardButton]] = []
	nav: list[InlineKeyboardButton] = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"sg:history:{page - 1}"))
	if total > (page + 1) * PAGE_SIZE:
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"sg:history:{page + 1}"))
	if nav:
		rows.append(nav)
	rows.append([
		InlineKeyboardButton("◀ Pending", callback_data="sg:pending:0"),
		InlineKeyboardButton("🔙 Back", callback_data="sg:menu"),
	])
	return InlineKeyboardMarkup(rows)


async def _render_pending(update: Update, context: CallbackContext, page: int) -> int:
	cq = update.callback_query
	jwt = await session.get_jwt(update.effective_user.id)
	if not jwt or cq is None or update.effective_chat is None:
		return ConversationHandler.END

	await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
	try:
		items, total = await _load_pending(jwt, page)
	except APIError as exc:
		if exc.status == 401 and update.effective_user is not None:
			await session.delete_jwt(update.effective_user.id)
			await cq.edit_message_text("Session expired. Tap /start to log in again.")
			return ConversationHandler.END
		await cq.answer(f"Could not load suggestions: {exc.detail}", show_alert=True)
		return SUGG_LIST

	context.user_data["sg_pending"] = items
	context.user_data["sg_pending_page"] = page
	context.user_data["sg_pending_total"] = total

	if not items:
		await cq.edit_message_text(
			"No pending suggestions right now.",
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton("📜 History", callback_data="sg:history:0")],
				[InlineKeyboardButton("🔙 Back", callback_data="sg:menu")],
			]),
		)
		return SUGG_LIST

	await cq.edit_message_text(
		_fmt_pending(items, page, total),
		parse_mode=ParseMode.HTML,
		reply_markup=_pending_keyboard(items, page, total),
	)
	return SUGG_LIST


async def _render_history(update: Update, context: CallbackContext, page: int) -> int:
	cq = update.callback_query
	jwt = await session.get_jwt(update.effective_user.id)
	if not jwt or cq is None or update.effective_chat is None:
		return ConversationHandler.END

	await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
	try:
		items, total = await _load_history(jwt, page)
	except APIError as exc:
		await cq.answer(f"Could not load history: {exc.detail}", show_alert=True)
		return SUGG_HISTORY

	context.user_data["sg_history"] = items
	context.user_data["sg_history_page"] = page
	context.user_data["sg_history_total"] = total

	await cq.edit_message_text(
		_fmt_history(items, page, total),
		parse_mode=ParseMode.HTML,
		reply_markup=_history_keyboard(page, total),
	)
	return SUGG_HISTORY


async def sugg_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _jwt(update)
	if not jwt or update.effective_chat is None or update.callback_query is not None:
		return ConversationHandler.END

	await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
	try:
		items, total = await _load_pending(jwt, 0)
	except APIError as exc:
		if exc.status == 401 and update.effective_user is not None:
			await session.delete_jwt(update.effective_user.id)
		await update.effective_message.reply_text(f"Could not load suggestions: {exc.detail}", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	context.user_data["sg_pending"] = items
	context.user_data["sg_pending_page"] = 0
	context.user_data["sg_pending_total"] = total

	if not items:
		await update.effective_message.reply_text(
			"No pending suggestions right now.",
			reply_markup=MAIN_MENU,
		)
		return ConversationHandler.END

	await update.effective_message.reply_text(
		_fmt_pending(items, 0, total),
		parse_mode=ParseMode.HTML,
		reply_markup=_pending_keyboard(items, 0, total),
	)
	return SUGG_LIST


async def sugg_callback(update: Update, context: CallbackContext) -> int:
	cq = update.callback_query
	if cq is None or update.effective_user is None or update.effective_chat is None:
		return ConversationHandler.END
	await cq.answer()
	jwt = await session.get_jwt(update.effective_user.id)
	if not jwt:
		await cq.edit_message_text("Session expired. Tap /start to log in again.")
		return ConversationHandler.END

	data = cq.data or ""
	if data == "sg:noop":
		return SUGG_LIST

	if data == "sg:menu":
		await cq.edit_message_text("Returning to main menu.")
		await context.bot.send_message(update.effective_chat.id, "What would you like to do?", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	if data.startswith("sg:reload:"):
		page = int(data.split(":")[-1])
		return await _render_pending(update, context, page)

	if data.startswith("sg:list:"):
		page = int(data.split(":")[-1])
		return await _render_pending(update, context, page)

	if data.startswith("sg:pending:"):
		page = int(data.split(":")[-1])
		return await _render_pending(update, context, page)

	if data.startswith("sg:history:"):
		page = int(data.split(":")[-1])
		return await _render_history(update, context, page)

	if data.startswith("sg:approve:"):
		parts = data.split(":")
		sid = parts[2]
		page = int(parts[3])
		try:
			await _approve(jwt, sid)
		except APIError as exc:
			await cq.answer(f"Approve failed: {exc.detail}", show_alert=True)
			return SUGG_LIST
		await cq.answer("✅ Approved", show_alert=False)
		return await _render_pending(update, context, page)

	if data.startswith("sg:reject_ask:"):
		parts = data.split(":")
		sid = parts[2]
		page = int(parts[3])
		context.user_data["sg_reject_id"] = sid
		context.user_data["sg_reject_page"] = page
		await cq.edit_message_text(
			"❌ <b>Reject suggestion</b>\n\nSend an optional comment, or tap Skip.",
			parse_mode=ParseMode.HTML,
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton("Skip", callback_data=f"sg:reject_do:{sid}:{page}:")],
				[InlineKeyboardButton("❌ Cancel", callback_data=f"sg:list:{page}")],
			]),
		)
		return SUGG_REJECT

	if data.startswith("sg:reject_do:"):
		parts = data.split(":", 4)
		sid = parts[2]
		page = int(parts[3])
		comment = parts[4] if len(parts) > 4 else ""
		try:
			await _reject(jwt, sid, comment)
		except APIError as exc:
			await cq.answer(f"Reject failed: {exc.detail}", show_alert=True)
			return SUGG_LIST
		await cq.answer("❌ Rejected", show_alert=False)
		context.user_data.pop("sg_reject_id", None)
		context.user_data.pop("sg_reject_page", None)
		return await _render_pending(update, context, page)

	return SUGG_LIST


async def sugg_reject_comment(update: Update, context: CallbackContext) -> int:
	jwt = await session.get_jwt(update.effective_user.id)
	if not jwt or update.effective_message is None:
		return ConversationHandler.END

	comment = (update.effective_message.text or "").strip()[:256]
	sid = context.user_data.get("sg_reject_id", "")
	page = int(context.user_data.get("sg_reject_page", 0))

	if not sid:
		await update.effective_message.reply_text("Nothing to reject.", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	try:
		await _reject(jwt, sid, comment)
	except APIError as exc:
		await update.effective_message.reply_text(f"Reject failed: {exc.detail}", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	context.user_data.pop("sg_reject_id", None)
	context.user_data.pop("sg_reject_page", None)
	await update.effective_message.reply_text(
		f"❌ Rejected{f' with comment: {html.escape(comment)}' if comment else ''}",
		parse_mode=ParseMode.HTML,
		reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ Back to suggestions", callback_data=f"sg:list:{page}")]]),
	)
	return SUGG_LIST


async def sugg_back(update: Update, context: CallbackContext) -> int:
	for key in ("sg_pending", "sg_pending_page", "sg_pending_total", "sg_history", "sg_history_page", "sg_history_total", "sg_reject_id", "sg_reject_page"):
		context.user_data.pop(key, None)
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_suggestions_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")

	return ConversationHandler(
		entry_points=[MessageHandler(filters.Regex(r"^(💡 Suggestions|🧠 Suggestions)$"), sugg_entry)],
		states={
			SUGG_LIST: [
				CallbackQueryHandler(sugg_callback, pattern=r"^sg:"),
				MessageHandler(back_filter, sugg_back),
			],
			SUGG_HISTORY: [
				CallbackQueryHandler(sugg_callback, pattern=r"^sg:"),
				MessageHandler(back_filter, sugg_back),
			],
			SUGG_REJECT: [
				CallbackQueryHandler(sugg_callback, pattern=r"^sg:"),
				MessageHandler(back_filter, sugg_back),
				MessageHandler(filters.TEXT & ~filters.COMMAND & ~back_filter, sugg_reject_comment),
			],
		},
		fallbacks=[MessageHandler(back_filter, sugg_back)],
		persistent=True,
		name="suggestions_conversation",
	)