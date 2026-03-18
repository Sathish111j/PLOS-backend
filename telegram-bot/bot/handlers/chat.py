"""Chat / RAG handler 

Flow:
  User taps "💬 Chat"     → enters chat mode, session_id loaded from Redis
  User sends a message    → POST /chat with session_id → reply with answer
  User taps "🔄 New chat" → clears session_id from Redis, starts fresh
  User taps "🔙 Back"     → returns to main menu

The chat session_id returned by the API is persisted in Redis under
ctx:{tg_user_id}:chat_session so it survives bot restarts.

Sources returned by the API are shown as a compact inline list so the
user can tap any of them to ask a follow-up.
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

CHATTING = 10

CHAT_MENU_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🔄 New conversation", callback_data="chat:new"),
            InlineKeyboardButton("🔙 Back to menu", callback_data="chat:back"),
        ]
    ]
)


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


def _format_sources(sources: list[dict]) -> str:
	if not sources:
		return ""
	lines = ["\n\n📎 *Sources:*"]
	for i, src in enumerate(sources[:5], 1):
		title = src.get("title") or src.get("name") or f"Source {i}"
		title = title[:60]
		lines.append(f"  {i}\\. {title}")
	return "\n".join(lines)


def _escape_md(text: str) -> str:
	"""Minimal MarkdownV2 escaping for API text responses."""
	for ch in r"_*[]()~`>#+-=|{}.!":
		text = text.replace(ch, f"\\{ch}")
	return text


async def chat_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _get_jwt_or_end(update)
	if not jwt:
		return ConversationHandler.END

	uid = update.effective_user.id if update.effective_user else None
	session_id = await session.get_ctx(uid, "chat_session_id") if uid is not None else None

	status = (
		"Continuing your last conversation."
		if session_id
		else "Starting a new conversation. Ask me anything about your knowledge base."
	)

	if update.effective_message:
		await update.effective_message.reply_text(
			f"💬 *Chat mode*\n{status}",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=CHAT_MENU_KEYBOARD,
		)
	return CHATTING


async def chat_message(update: Update, context: CallbackContext) -> int:
	jwt = await _get_jwt_or_end(update)
	if not jwt or update.effective_user is None or update.effective_message is None or update.effective_chat is None:
		return ConversationHandler.END

	uid = update.effective_user.id
	query = (update.effective_message.text or "").strip()
	session_id = await session.get_ctx(uid, "chat_session_id")

	await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

	try:
		result = await api.chat(jwt, query, session_id=session_id)
	except APIError as exc:
		if exc.status == 401:
			await session.delete_jwt(uid)
			await update.effective_message.reply_text(
				"Session expired. Tap /start to log in again.",
				reply_markup=WELCOME_KEYBOARD,
			)
			return ConversationHandler.END
		log.warning("chat API error: %s", exc)
		await update.effective_message.reply_text(
			f"Something went wrong: {exc.detail}\n\nTry again or tap Back to menu.",
			reply_markup=CHAT_MENU_KEYBOARD,
		)
		return CHATTING

	new_session_id = result.get("session_id") or session_id
	if new_session_id:
		await session.set_ctx(uid, "chat_session_id", new_session_id)

	answer = result.get("answer") or result.get("response") or result.get("message", "")
	sources = result.get("sources") or result.get("references") or []

	if not answer:
		await update.effective_message.reply_text(
			"I didn't get a response from the knowledge base. Try rephrasing your question.",
			reply_markup=CHAT_MENU_KEYBOARD,
		)
		return CHATTING

	max_len = 3800
	suffix = "\n\n_…response truncated. Ask me to continue._"
	if len(answer) > max_len:
		answer = answer[:max_len] + suffix

	reply = answer + _format_sources(sources)

	try:
		await update.effective_message.reply_text(
			reply,
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=CHAT_MENU_KEYBOARD,
		)
	except Exception:
		await update.effective_message.reply_text(answer, reply_markup=CHAT_MENU_KEYBOARD)

	return CHATTING


async def chat_callback(update: Update, context: CallbackContext) -> int:
	query = update.callback_query
	if query is None or update.effective_user is None or update.effective_chat is None:
		return ConversationHandler.END
	await query.answer()

	uid = update.effective_user.id
	data = query.data or ""

	if data == "chat:new":
		await session.clear_ctx_key(uid, "chat_session_id")
		await query.edit_message_text(
			"💬 *New conversation started.*\nAsk me anything about your knowledge base.",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=CHAT_MENU_KEYBOARD,
		)
		return CHATTING

	if data == "chat:back":
		await query.edit_message_text("Returning to main menu.")
		await context.bot.send_message(
			chat_id=update.effective_chat.id,
			text="What would you like to do?",
			reply_markup=MAIN_MENU,
		)
		return ConversationHandler.END

	return CHATTING


async def chat_back_text(update: Update, context: CallbackContext) -> int:
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_chat_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")

	return ConversationHandler(
		entry_points=[MessageHandler(filters.Regex(r"^💬 Chat$"), chat_entry)],
		states={
			CHATTING: [
				CallbackQueryHandler(chat_callback, pattern=r"^chat:"),
				MessageHandler(back_filter, chat_back_text),
				MessageHandler(filters.TEXT & ~filters.COMMAND & ~back_filter, chat_message),
			],
		},
		fallbacks=[MessageHandler(back_filter, chat_back_text)],
		persistent=True,
		name="chat_conversation",
	)