"""Auth handler — ConversationHandler states for sign-up and login.

Sign-up flow:   SIGNUP_EMAIL → SIGNUP_USERNAME → SIGNUP_PASSWORD → done
Login flow:     LOGIN_EMAIL  → LOGIN_PASSWORD  → done

Security:
  - The user's password message is deleted from the chat immediately after
    reading. It is never logged.
  - Intermediate state (email, username) is stored only in
    ConversationHandler's user_data dict — lives in memory only during the
    conversation, never persisted.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, CommandHandler, ConversationHandler, MessageHandler, filters

import bot.api_client as api
from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import CANCEL_KEYBOARD, MAIN_MENU, WELCOME_KEYBOARD

log = logging.getLogger(__name__)

# ── States ────────────────────────────────────────────────────────────────────
SIGNUP_EMAIL, SIGNUP_USERNAME, SIGNUP_PASSWORD = range(3)
LOGIN_EMAIL, LOGIN_PASSWORD = range(3, 5)

# ── Helpers ───────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _tg_id(update: Update) -> int:
	return update.effective_user.id


async def _cancel(update: Update, context: CallbackContext) -> int:
	context.user_data.clear()
	if update.effective_message:
		await update.effective_message.reply_text(
			"Cancelled. You can sign up or log in whenever you're ready.",
			reply_markup=WELCOME_KEYBOARD,
		)
	return ConversationHandler.END


async def _already_authenticated(update: Update) -> bool:
	if await session.is_authenticated(_tg_id(update)):
		if update.effective_message:
			await update.effective_message.reply_text(
				"You're already logged in. Use /logout first to switch accounts.",
				reply_markup=MAIN_MENU,
			)
		return True
	return False


def _extract_token(payload: dict) -> str:
	"""Extract a JWT from common API response shapes.

	Supports flat and nested payloads such as:
	- {"access_token": "..."}
	- {"token": "..."}
	- {"jwt": "..."}
	- {"data": {"access_token": "..."}}
	- {"result": {"token": "..."}}
	"""
	for candidate in (payload, payload.get("data"), payload.get("result"), payload.get("body")):
		if isinstance(candidate, dict):
			token = candidate.get("access_token") or candidate.get("token") or candidate.get("jwt")
			if token:
				return str(token)
	return ""


# ── /start ────────────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: CallbackContext) -> None:
	if update.effective_message is None:
		return

	if await session.is_authenticated(_tg_id(update)):
		await update.effective_message.reply_text(
			f"Welcome back, {update.effective_user.first_name}! What would you like to do?",
			reply_markup=MAIN_MENU,
		)
		return

	await update.effective_message.reply_text(
		"👋 *Welcome to your Knowledge Base bot!*\n\n"
		"Sign up for a new account or log in to an existing one.",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=WELCOME_KEYBOARD,
	)


# ── /logout ───────────────────────────────────────────────────────────────────


async def cmd_logout(update: Update, context: CallbackContext) -> None:
	if update.effective_user is not None:
		await session.delete_jwt(_tg_id(update))
	if update.effective_message:
		await update.effective_message.reply_text(
			"You've been logged out. See you next time!",
			reply_markup=WELCOME_KEYBOARD,
		)


# ── Sign-up flow ──────────────────────────────────────────────────────────────


async def signup_start(update: Update, context: CallbackContext) -> int:
	if await _already_authenticated(update):
		return ConversationHandler.END

	if update.effective_message:
		await update.effective_message.reply_text(
			"Let's create your account.\n\nWhat's your *email address*?",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=CANCEL_KEYBOARD,
		)
	return SIGNUP_EMAIL


async def signup_email(update: Update, context: CallbackContext) -> int:
	email = (update.effective_message.text or "").strip()

	if not EMAIL_RE.match(email):
		await update.effective_message.reply_text(
			"That doesn't look like a valid email. Please try again."
		)
		return SIGNUP_EMAIL

	context.user_data["signup_email"] = email
	await update.effective_message.reply_text(
		"Got it! Now choose a *username* (letters, numbers, underscores only):",
		parse_mode=ParseMode.MARKDOWN,
	)
	return SIGNUP_USERNAME


async def signup_username(update: Update, context: CallbackContext) -> int:
	username = (update.effective_message.text or "").strip()

	if not re.match(r"^\w{3,32}$", username):
		await update.effective_message.reply_text(
			"Username must be 3–32 characters and contain only letters, numbers, or underscores. Try again:"
		)
		return SIGNUP_USERNAME

	context.user_data["signup_username"] = username
	await update.effective_message.reply_text(
		"Almost there! Choose a *password* (min 8 characters):\n\n"
		"_Your message will be deleted immediately after reading._",
		parse_mode=ParseMode.MARKDOWN,
	)
	return SIGNUP_PASSWORD


async def signup_password(update: Update, context: CallbackContext) -> int:
	password = update.effective_message.text or ""

	try:
		await update.effective_message.delete()
	except Exception:
		pass

	if len(password) < 8:
		await update.effective_chat.send_message(
			"Password must be at least 8 characters. Please try again:"
		)
		return SIGNUP_PASSWORD

	email = context.user_data.pop("signup_email", "")
	username = context.user_data.pop("signup_username", "")

	try:
		result = await api.register(email=email, username=username, password=password)
	except APIError as exc:
		log.warning("register failed for %s: %s", email, exc)
		await update.effective_chat.send_message(
			f"Registration failed: {exc.detail}\n\nTap /start to try again.",
			reply_markup=WELCOME_KEYBOARD,
		)
		return ConversationHandler.END

	log.info("AUTH RESPONSE (register) keys=%s", list(result.keys()))

	jwt = _extract_token(result)
	if not jwt:
		log.error("register response missing token: %s", result)
		await update.effective_chat.send_message(
			"Something went wrong — no token returned. Please try again later."
		)
		return ConversationHandler.END

	await session.set_jwt(_tg_id(update), jwt)
	display = result.get("user", {}).get("username", username)

	await update.effective_chat.send_message(
		f"✅ Account created! Welcome, *{display}*.\n\n"
		"You can now send me anything — text, files, links, voice messages — and I'll add it to your knowledge base.",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=MAIN_MENU,
	)
	return ConversationHandler.END


# ── Login flow ────────────────────────────────────────────────────────────────


async def login_start(update: Update, context: CallbackContext) -> int:
	if await _already_authenticated(update):
		return ConversationHandler.END

	if update.effective_message:
		await update.effective_message.reply_text(
			"Welcome back! What's your *email address*?",
			parse_mode=ParseMode.MARKDOWN,
			reply_markup=CANCEL_KEYBOARD,
		)
	return LOGIN_EMAIL


async def login_email(update: Update, context: CallbackContext) -> int:
	email = (update.effective_message.text or "").strip()

	if not EMAIL_RE.match(email):
		await update.effective_message.reply_text(
			"That doesn't look like a valid email. Please try again."
		)
		return LOGIN_EMAIL

	context.user_data["login_email"] = email
	await update.effective_message.reply_text(
		"Got it. Now enter your *password*:\n\n"
		"_Your message will be deleted immediately after reading._",
		parse_mode=ParseMode.MARKDOWN,
	)
	return LOGIN_PASSWORD


async def login_password(update: Update, context: CallbackContext) -> int:
	password = update.effective_message.text or ""
	email = context.user_data.pop("login_email", "")

	try:
		await update.effective_message.delete()
	except Exception:
		pass

	try:
		result = await api.login(email=email, password=password)
	except APIError as exc:
		log.warning("login failed for %s: %s", email, exc)
		msg = (
			"Incorrect email or password. Please try again — tap /start."
			if exc.status in (401, 403)
			else f"Login failed: {exc.detail}. Tap /start to retry."
		)
		await update.effective_chat.send_message(msg, reply_markup=WELCOME_KEYBOARD)
		return ConversationHandler.END

	log.info("AUTH RESPONSE (login) keys=%s", list(result.keys()))

	jwt = _extract_token(result)
	if not jwt:
		log.error("login response missing token: %s", result)
		await update.effective_chat.send_message(
			"Something went wrong — no token returned. Please try again later."
		)
		return ConversationHandler.END

	await session.set_jwt(_tg_id(update), jwt)
	display = result.get("user", {}).get("username", email.split("@")[0])

	await update.effective_chat.send_message(
		f"✅ Logged in! Welcome back, *{display}*.",
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=MAIN_MENU,
	)
	return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────


def build_auth_conversation() -> ConversationHandler:
	cancel_filter = filters.Regex(r"^❌ Cancel$")

	return ConversationHandler(
		entry_points=[
			CommandHandler("start", cmd_start),
			MessageHandler(filters.Regex(r"^✍️ Sign up$"), signup_start),
			MessageHandler(filters.Regex(r"^🔑 Login$"), login_start),
		],
		states={
			SIGNUP_EMAIL: [MessageHandler(filters.TEXT & ~cancel_filter, signup_email)],
			SIGNUP_USERNAME: [MessageHandler(filters.TEXT & ~cancel_filter, signup_username)],
			SIGNUP_PASSWORD: [MessageHandler(filters.TEXT & ~cancel_filter, signup_password)],
			LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~cancel_filter, login_email)],
			LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~cancel_filter, login_password)],
		},
		fallbacks=[
			CommandHandler("cancel", _cancel),
			MessageHandler(cancel_filter, _cancel),
		],
		persistent=True,
		name="auth_conversation",
	)
