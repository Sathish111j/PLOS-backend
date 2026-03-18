"""

Flow:
  User taps "🗂 Buckets"     → paginated bucket list (GET /buckets)
  User taps a bucket         → items inside it (GET /buckets/{id}/items)
  User taps an item          → item detail with move/delete options
  User taps "Move"           → bucket picker → PATCH /items/{id}/move
  User taps "Delete"         → confirm → DELETE /items/{id}
  User taps "🔙 Back"        → one level up

Also handles the hand-off from the search handler:
  callback_data="sr:bucket:{id}" → jumps straight into a bucket's item list.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler, ConversationHandler, MessageHandler, filters

import bot.api_client as api
from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD

log = logging.getLogger(__name__)

BUCKET_LIST = 30
BUCKET_ITEMS = 31
ITEM_DETAIL = 32
ITEM_MOVE = 33

PAGE_SIZE = 6


async def _jwt(update: Update) -> str | None:
	uid = update.effective_user.id if update.effective_user else None
	if uid is None:
		return None
	jwt = await session.get_jwt(uid)
	if not jwt:
		target = update.effective_message or update.callback_query.message
		if target:
			await target.reply_text(
				"Session expired. Tap /start to log in again.",
				reply_markup=WELCOME_KEYBOARD,
			)
	return jwt


def _bucket_id(item: dict) -> str:
	return str(item.get("id") or item.get("bucket_id") or item.get("bucketId") or "")


def _item_id(item: dict) -> str:
	return str(item.get("id") or item.get("item_id") or item.get("document_id") or "")


def _buckets_kb(buckets: list[dict], page: int) -> InlineKeyboardMarkup:
	start = page * PAGE_SIZE
	slice_ = buckets[start : start + PAGE_SIZE]
	rows = []
	for bucket in slice_:
		bid = _bucket_id(bucket)
		name = bucket.get("name") or bucket.get("title") or "Unnamed"
		count = bucket.get("document_count") or bucket.get("item_count") or bucket.get("items_count") or ""
		label = f"📁 {name[:40]}" + (f"  ({count})" if count != "" else "")
		rows.append([InlineKeyboardButton(label, callback_data=f"bk:open:{bid}:{page}")])

	nav = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"bk:list:{page - 1}"))
	if start + PAGE_SIZE < len(buckets):
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"bk:list:{page + 1}"))
	if nav:
		rows.append(nav)

	rows.append([InlineKeyboardButton("🔙 Back to menu", callback_data="bk:menu")])
	return InlineKeyboardMarkup(rows)


def _items_kb(items: list[dict], page: int, bucket_id: str, back_page: int) -> InlineKeyboardMarkup:
	start = page * PAGE_SIZE
	slice_ = items[start : start + PAGE_SIZE]
	rows = []
	for item in slice_:
		iid = _item_id(item)
		title = item.get("filename") or item.get("title") or item.get("name") or "Untitled"
		label = f"📄 {title[:44]}"
		rows.append([InlineKeyboardButton(label, callback_data=f"bk:item:{iid}:{bucket_id}:{page}")])

	nav = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"bk:items:{bucket_id}:{page - 1}:{back_page}"))
	if start + PAGE_SIZE < len(items):
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"bk:items:{bucket_id}:{page + 1}:{back_page}"))
	if nav:
		rows.append(nav)

	rows.append([InlineKeyboardButton("🔙 Buckets", callback_data=f"bk:list:{back_page}")])
	return InlineKeyboardMarkup(rows)


def _item_detail_kb(item_id: str, bucket_id: str, items_page: int, back_page: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[
			[
				InlineKeyboardButton(
					"📦 Move",
					callback_data=f"bk:move_pick:{item_id}:{bucket_id}:{items_page}:{back_page}",
				),
				InlineKeyboardButton(
					"🗑 Delete",
					callback_data=f"bk:del_confirm:{item_id}:{bucket_id}:{items_page}:{back_page}",
				),
			],
			[InlineKeyboardButton("◀ Back to items", callback_data=f"bk:items:{bucket_id}:{items_page}:{back_page}")],
		]
	)


def _move_picker_kb(
	buckets: list[dict],
	item_id: str,
	current_bucket_id: str,
	items_page: int,
	back_page: int,
	) -> InlineKeyboardMarkup:
	rows = []
	for bucket in buckets:
		bid = _bucket_id(bucket)
		if bid == current_bucket_id:
			continue
		name = bucket.get("name") or bucket.get("title") or "Unnamed"
		rows.append([
			InlineKeyboardButton(
				f"📁 {name[:44]}",
				callback_data=f"bk:move_do:{item_id}:{bid}:{current_bucket_id}:{items_page}:{back_page}",
			),
		])
	rows.append([
		InlineKeyboardButton(
			"❌ Cancel",
			callback_data=f"bk:item:{item_id}:{current_bucket_id}:{items_page}",
		)
	])
	return InlineKeyboardMarkup(rows)


def _delete_confirm_kb(item_id: str, bucket_id: str, items_page: int, back_page: int) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[[
			InlineKeyboardButton("✅ Yes, delete", callback_data=f"bk:del_do:{item_id}:{bucket_id}:{items_page}:{back_page}"),
			InlineKeyboardButton("❌ Cancel", callback_data=f"bk:item:{item_id}:{bucket_id}:{items_page}"),
		]]
	)


def _fmt_item(item: dict) -> str:
	title = item.get("filename") or item.get("title") or item.get("name") or "Untitled"
	stype = item.get("content_type") or item.get("source_type") or item.get("type") or "—"
	bucket = item.get("bucket_name") or ""
	created = (item.get("created_at") or "")[:10]
	snippet = (item.get("text_preview") or item.get("snippet") or item.get("content") or "")[:300]

	lines = [f"*{title}*"]
	if bucket:
		lines.append(f"📁 {bucket}")
	lines.append(f"📄 Type: {stype}")
	if created:
		lines.append(f"🗓 {created}")
	if snippet:
		lines.append(f"\n_{snippet}_")
	return "\n".join(lines)


async def buckets_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _jwt(update)
	if not jwt:
		return ConversationHandler.END

	if update.effective_chat:
		await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

	try:
		data = await api.get_buckets(jwt)
	except APIError as exc:
		if exc.status == 401 and update.effective_user:
			await session.delete_jwt(update.effective_user.id)
		if update.effective_message:
			await update.effective_message.reply_text(
				f"Could not load buckets: {exc.detail}", reply_markup=MAIN_MENU
			)
		return ConversationHandler.END

	buckets = data.get("buckets") or data.get("items") or (data if isinstance(data, list) else [])
	context.user_data["bk_buckets"] = buckets

	if not buckets:
		if update.effective_message:
			await update.effective_message.reply_text(
				"No buckets found. Ingest some content first.",
				reply_markup=MAIN_MENU,
			)
		return ConversationHandler.END

	if update.effective_message:
		await update.effective_message.reply_text(
			f"🗂 *Your buckets* ({len(buckets)} total):",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_buckets_kb(buckets, page=0),
		)
	return BUCKET_LIST


async def buckets_callback(update: Update, context: CallbackContext) -> int:
	cq = update.callback_query
	if cq is None:
		return ConversationHandler.END
	await cq.answer()
	uid = update.effective_user.id if update.effective_user else None
	if uid is None:
		return ConversationHandler.END
	jwt = await session.get_jwt(uid)

	if not jwt:
		await cq.edit_message_text("Session expired. Tap /start to log in again.")
		return ConversationHandler.END

	data = cq.data or ""
	buckets = context.user_data.get("bk_buckets", [])

	if data == "bk:menu":
		await cq.edit_message_text("Returning to main menu.")
		await context.bot.send_message(update.effective_chat.id, "What would you like to do?", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	if data.startswith("bk:list:"):
		page = int(data.split(":")[-1])
		if not buckets:
			await cq.edit_message_text("Bucket list expired. Tap 🗂 Buckets to reload.")
			return ConversationHandler.END
		await cq.edit_message_text(
			f"🗂 *Your buckets* ({len(buckets)} total):",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_buckets_kb(buckets, page),
		)
		return BUCKET_LIST

	if data.startswith("bk:open:"):
		_, _, bucket_id, back_page_str = data.split(":", 3)
		back_page = int(back_page_str)

		if update.effective_chat:
			await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			bucket_obj = next((b for b in buckets if _bucket_id(b) == bucket_id), {})
			bucket_name = bucket_obj.get("name") or bucket_obj.get("title") or bucket_id
			items_data = await api.get_bucket_items(jwt, bucket_id)
		except APIError as exc:
			await cq.edit_message_text(f"Could not load bucket: {exc.detail}")
			return BUCKET_LIST

		items = items_data.get("items") or items_data.get("results") or (items_data if isinstance(items_data, list) else [])
		context.user_data["bk_items"] = items
		context.user_data["bk_bucket_id"] = bucket_id
		context.user_data["bk_bucket_name"] = bucket_name
		context.user_data["bk_back_page"] = back_page

		if not items:
			await cq.edit_message_text(
				f"📁 *{bucket_name}* is empty.",
				parse_mode=ParseMode.MARKDOWN,
				reply_markup=InlineKeyboardMarkup([
					[InlineKeyboardButton("🔙 Buckets", callback_data=f"bk:list:{back_page}")]
				]),
			)
			return BUCKET_ITEMS

		await cq.edit_message_text(
			f"📁 *{bucket_name}*  —  {len(items)} item{'s' if len(items) != 1 else ''}:",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_items_kb(items, 0, bucket_id, back_page),
		)
		return BUCKET_ITEMS

	if data.startswith("bk:items:"):
		parts = data.split(":")
		bucket_id = parts[2]
		page = int(parts[3])
		back_page = int(parts[4])
		items = context.user_data.get("bk_items", [])
		name = context.user_data.get("bk_bucket_name", bucket_id)

		await cq.edit_message_text(
			f"📁 *{name}*  —  {len(items)} item{'s' if len(items) != 1 else ''}:",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_items_kb(items, page, bucket_id, back_page),
		)
		return BUCKET_ITEMS

	if data.startswith("bk:item:"):
		parts = data.split(":")
		item_id = parts[2]
		bucket_id = parts[3]
		items_page = int(parts[4])
		back_page = context.user_data.get("bk_back_page", 0)
		items = context.user_data.get("bk_items", [])

		item = next((i for i in items if _item_id(i) == item_id), None)
		if not item:
			await cq.edit_message_text("Item not found — go back and try again.")
			return BUCKET_ITEMS

		await cq.edit_message_text(
			_fmt_item(item),
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_item_detail_kb(item_id, bucket_id, items_page, back_page),
		)
		return ITEM_DETAIL

	if data.startswith("bk:move_pick:"):
		parts = data.split(":")
		item_id = parts[2]
		bucket_id = parts[3]
		items_page = int(parts[4])
		back_page = int(parts[5])

		await cq.edit_message_text(
			"📦 Move item to which bucket?",
			reply_markup=_move_picker_kb(buckets, item_id, bucket_id, items_page, back_page),
		)
		return ITEM_MOVE

	if data.startswith("bk:move_do:"):
		parts = data.split(":")
		item_id = parts[2]
		target_bucket = parts[3]
		current_bucket = parts[4]
		items_page = int(parts[5])
		back_page = int(parts[6])

		try:
			await api.move_item(jwt, item_id, target_bucket)
		except APIError as exc:
			await cq.edit_message_text(f"Move failed: {exc.detail}")
			return ITEM_DETAIL

		context.user_data["bk_items"] = [i for i in context.user_data.get("bk_items", []) if _item_id(i) != item_id]
		target_name = next((b.get("name") or b.get("title") for b in buckets if _bucket_id(b) == target_bucket), target_bucket)

		await cq.edit_message_text(
			f"✅ Item moved to *{target_name}*.",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton("◀ Back to items", callback_data=f"bk:items:{current_bucket}:{items_page}:{back_page}")]
			]),
		)
		return BUCKET_ITEMS

	if data.startswith("bk:del_confirm:"):
		parts = data.split(":")
		item_id = parts[2]
		bucket_id = parts[3]
		items_page = int(parts[4])
		back_page = int(parts[5])

		await cq.edit_message_text(
			"🗑 *Delete this item?* This cannot be undone.",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_delete_confirm_kb(item_id, bucket_id, items_page, back_page),
		)
		return ITEM_DETAIL

	if data.startswith("bk:del_do:"):
		parts = data.split(":")
		item_id = parts[2]
		bucket_id = parts[3]
		items_page = int(parts[4])
		back_page = int(parts[5])

		try:
			await api.delete_item(jwt, item_id)
		except APIError as exc:
			await cq.edit_message_text(f"Delete failed: {exc.detail}")
			return ITEM_DETAIL

		context.user_data["bk_items"] = [i for i in context.user_data.get("bk_items", []) if _item_id(i) != item_id]

		await cq.edit_message_text(
			"🗑 Item deleted.",
			reply_markup=InlineKeyboardMarkup([
				[InlineKeyboardButton("◀ Back to items", callback_data=f"bk:items:{bucket_id}:{items_page}:{back_page}")]
			]),
		)
		return BUCKET_ITEMS

	if data.startswith("sr:bucket:"):
		bucket_id = data.split(":", 2)[-1]

		if update.effective_chat:
			await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			items_data = await api.get_bucket_items(jwt, bucket_id)
		except APIError as exc:
			await cq.edit_message_text(f"Could not load bucket: {exc.detail}")
			return ConversationHandler.END

		items = items_data.get("items") or items_data.get("results") or (items_data if isinstance(items_data, list) else [])
		context.user_data["bk_items"] = items
		context.user_data["bk_bucket_id"] = bucket_id
		context.user_data["bk_bucket_name"] = bucket_id
		context.user_data["bk_back_page"] = 0

		await cq.edit_message_text(
			f"📁 *Bucket {bucket_id}*  —  {len(items)} item{'s' if len(items) != 1 else ''}:",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=_items_kb(items, 0, bucket_id, 0),
		)
		return BUCKET_ITEMS

	return BUCKET_LIST


async def buckets_back(update: Update, context: CallbackContext) -> int:
	context.user_data.pop("bk_buckets", None)
	context.user_data.pop("bk_items", None)
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_buckets_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")
	return ConversationHandler(
		entry_points=[
			MessageHandler(filters.Regex(r"^🗂️? Buckets$"), buckets_entry),
			CallbackQueryHandler(buckets_callback, pattern=r"^sr:bucket:"),
		],
		states={
			BUCKET_LIST: [CallbackQueryHandler(buckets_callback, pattern=r"^bk:"), MessageHandler(back_filter, buckets_back)],
			BUCKET_ITEMS: [CallbackQueryHandler(buckets_callback, pattern=r"^bk:"), MessageHandler(back_filter, buckets_back)],
			ITEM_DETAIL: [CallbackQueryHandler(buckets_callback, pattern=r"^bk:"), MessageHandler(back_filter, buckets_back)],
			ITEM_MOVE: [CallbackQueryHandler(buckets_callback, pattern=r"^bk:"), MessageHandler(back_filter, buckets_back)],
		},
		fallbacks=[MessageHandler(back_filter, buckets_back)],
		persistent=True,
		name="buckets_conversation",
	)
