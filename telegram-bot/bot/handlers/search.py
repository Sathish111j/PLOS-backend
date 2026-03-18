"""Search handler 

Flow:
  User taps "🔍 Search"   → enters search mode
  User types a query      → POST /search → paginated inline results
  User taps a result      → shows item detail + "View bucket" button
  User taps "🔙 Back"     → returns to main menu
  User taps "Next page"   → fetches next page of results (stored in user_data)

Results are shown as an InlineKeyboardMarkup so the user can tap
any of them without leaving the conversation. Each result button
stores the item_id in its callback_data.

Pagination is handled client-side: the full result list is stored in
context.user_data["search_results"] and sliced per page — avoids
making extra API calls for paging.
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

import bot.api_client as api
from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD

log = logging.getLogger(__name__)

SEARCH_QUERY = 20
SEARCH_RESULT = 21

PAGE_SIZE = 5


async def _get_jwt_or_end(update: Update) -> str | None:
	uid = update.effective_user.id if update.effective_user else None
	if uid is None:
		return None
	jwt = await session.get_jwt(uid)
	if not jwt and update.effective_message:
		await update.effective_message.reply_text(
			"Session expired. Tap /start to log in again.",
			reply_markup=WELCOME_KEYBOARD,
		)
	return jwt


def _results_keyboard(results: list[dict], page: int) -> InlineKeyboardMarkup:
	start = page * PAGE_SIZE
	slice_ = results[start : start + PAGE_SIZE]
	total = len(results)

	rows = []
	for item in slice_:
		item_id = item.get("id") or item.get("item_id") or item.get("document_id") or ""
		title = item.get("title") or item.get("name") or item.get("filename") or "Untitled"
		score = item.get("score") or item.get("relevance", 0)
		score_str = f" ({score:.0%})" if isinstance(score, (int, float)) and score else ""
		label = f"{title[:45]}{score_str}"
		rows.append([InlineKeyboardButton(label, callback_data=f"sr:item:{item_id}")])

	nav = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"sr:page:{page - 1}"))
	if start + PAGE_SIZE < total:
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"sr:page:{page + 1}"))
	if nav:
		rows.append(nav)

	rows.append([
		InlineKeyboardButton("🔍 New search", callback_data="sr:new"),
		InlineKeyboardButton("🔙 Back", callback_data="sr:back"),
	])
	return InlineKeyboardMarkup(rows)


def _item_detail_keyboard(bucket_id: str | None) -> InlineKeyboardMarkup:
	rows = []
	if bucket_id:
		rows.append([InlineKeyboardButton("🗂 View bucket", callback_data=f"sr:bucket:{bucket_id}")])
	rows.append([
		InlineKeyboardButton("◀ Back to results", callback_data="sr:results"),
		InlineKeyboardButton("🔙 Menu", callback_data="sr:back"),
	])
	return InlineKeyboardMarkup(rows)


def _format_item(item: dict) -> str:
	title = item.get("title") or item.get("name") or item.get("filename") or "Untitled"
	snippet = item.get("snippet") or item.get("text_preview") or item.get("content", "")[:400]
	bucket = item.get("bucket_name") or item.get("bucket") or ""
	source = item.get("source_type") or item.get("type") or ""
	created = item.get("created_at", "")[:10] if item.get("created_at") else ""

	lines = [f"*{title}*"]
	if bucket:
		lines.append(f"📁 Bucket: {bucket}")
	if source:
		lines.append(f"📄 Type: {source}")
	if created:
		lines.append(f"🗓 Added: {created}")
	if snippet:
		lines.append(f"\n{snippet}")
	return "\n".join(lines)


async def search_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _get_jwt_or_end(update)
	if not jwt or update.effective_message is None:
		return ConversationHandler.END

	context.user_data.pop("search_results", None)
	context.user_data.pop("search_page", None)
	context.user_data.pop("search_query", None)

	await update.effective_message.reply_text(
		"🔍 *Search mode*\n\nWhat would you like to find in your knowledge base?",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to menu", callback_data="sr:back")]]),
	)
	return SEARCH_QUERY


async def search_query(update: Update, context: CallbackContext) -> int:
	jwt = await _get_jwt_or_end(update)
	if not jwt or update.effective_message is None or update.effective_chat is None:
		return ConversationHandler.END

	query = (update.effective_message.text or "").strip()
	if not query:
		await update.effective_message.reply_text("Please enter a search term.")
		return SEARCH_QUERY

	await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

	try:
		data = await api.search(jwt, query)
	except APIError as exc:
		if exc.status == 401 and update.effective_user is not None:
			await session.delete_jwt(update.effective_user.id)
			await update.effective_message.reply_text(
				"Session expired. Tap /start to log in again.",
				reply_markup=WELCOME_KEYBOARD,
			)
			return ConversationHandler.END
		log.warning("search API error: %s", exc)
		await update.effective_message.reply_text(
			f"Search failed: {exc.detail}",
			reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to menu", callback_data="sr:back")]]),
		)
		return SEARCH_QUERY

	results = data.get("results") or data.get("items") or []

	if not results:
		await update.effective_message.reply_text(
			f'No results found for "*{query}*". Try different keywords.',
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton("🔍 Try again", callback_data="sr:new"), InlineKeyboardButton("🔙 Back", callback_data="sr:back")]
			]),
		)
		return SEARCH_RESULT

	context.user_data["search_results"] = results
	context.user_data["search_page"] = 0
	context.user_data["search_query"] = query

	total = len(results)
	await update.effective_message.reply_text(
		f'Found *{total}* result{"s" if total != 1 else ""} for "*{query}*":',
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=_results_keyboard(results, page=0),
	)
	return SEARCH_RESULT


async def search_callback(update: Update, context: CallbackContext) -> int:
	cq = update.callback_query
	if cq is None or update.effective_user is None or update.effective_chat is None:
		return ConversationHandler.END
	await cq.answer()

	jwt = await session.get_jwt(update.effective_user.id)
	if not jwt:
		await cq.edit_message_text("Session expired. Tap /start to log in again.")
		return ConversationHandler.END

	data = cq.data or ""
	results = context.user_data.get("search_results", [])
	page = context.user_data.get("search_page", 0)
	query = context.user_data.get("search_query", "")

	if data.startswith("sr:page:"):
		new_page = int(data.split(":")[-1])
		context.user_data["search_page"] = new_page
		total = len(results)
		await cq.edit_message_text(
			f'Found *{total}* result{"s" if total != 1 else ""} for "*{query}*":',
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_results_keyboard(results, page=new_page),
		)
		return SEARCH_RESULT

	if data.startswith("sr:item:"):
		item_id = data.split(":", 2)[-1]
		item = next((r for r in results if str(r.get("id") or r.get("item_id") or r.get("document_id")) == item_id), None)
		if not item:
			await cq.edit_message_text("Item not found — try a new search.")
			return SEARCH_RESULT

		bucket_id = item.get("bucket_id") or item.get("bucket")
		context.user_data["last_item"] = item

		await cq.edit_message_text(
			_format_item(item),
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_item_detail_keyboard(str(bucket_id) if bucket_id else None),
		)
		return SEARCH_RESULT

	if data == "sr:results":
		if not results:
			await cq.edit_message_text(
				"No cached results. Start a new search.",
				reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 Search", callback_data="sr:new")]]),
			)
			return SEARCH_RESULT

		total = len(results)
		await cq.edit_message_text(
			f'Found *{total}* result{"s" if total != 1 else ""} for "*{query}*":',
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_results_keyboard(results, page=page),
		)
		return SEARCH_RESULT

	if data == "sr:new":
		context.user_data.pop("search_results", None)
		context.user_data.pop("search_page", None)
		context.user_data.pop("search_query", None)
		await cq.edit_message_text(
			"🔍 *Search mode*\n\nWhat would you like to find?",
			parse_mode=ParseMode.MARKDOWN,
		)
		return SEARCH_QUERY

	if data == "sr:back":
		await cq.edit_message_text("Returning to main menu.")
		await context.bot.send_message(chat_id=update.effective_chat.id, text="What would you like to do?", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	if data.startswith("sr:bucket:"):
		bucket_id = data.split(":", 2)[-1]
		await cq.edit_message_text(
			f"Bucket viewer coming next.\nBucket ID: {bucket_id}",
			reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="sr:results")]]),
		)
		return SEARCH_RESULT

	return SEARCH_RESULT


async def search_back_text(update: Update, context: CallbackContext) -> int:
	context.user_data.pop("search_results", None)
	context.user_data.pop("search_page", None)
	context.user_data.pop("search_query", None)
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_search_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")

	return ConversationHandler(
		entry_points=[MessageHandler(filters.Regex(r"^🔍 Search$"), search_entry)],
		states={
			SEARCH_QUERY: [
				CallbackQueryHandler(search_callback, pattern=r"^sr:"),
				MessageHandler(back_filter, search_back_text),
				MessageHandler(filters.TEXT & ~filters.COMMAND & ~back_filter, search_query),
			],
			SEARCH_RESULT: [
				CallbackQueryHandler(search_callback, pattern=r"^sr:"),
				MessageHandler(back_filter, search_back_text),
				MessageHandler(filters.TEXT & ~filters.COMMAND & ~back_filter, search_query),
			],
		},
		fallbacks=[MessageHandler(back_filter, search_back_text)],
		persistent=True,
		name="search_conversation",
	)