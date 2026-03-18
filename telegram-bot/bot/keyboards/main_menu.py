"""Reply and inline keyboards used by the Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


MAIN_MENU = ReplyKeyboardMarkup(
	keyboard=[
		["💬 Chat", "🔍 Search"],
		["🗂 Buckets", "💡 Suggestions"],
		["📥 Ingest jobs", "⚙️ Settings"],
	],
	resize_keyboard=True,
	is_persistent=True,
	input_field_placeholder="Choose an option or just send anything to ingest it…",
)

WELCOME_KEYBOARD = ReplyKeyboardMarkup(
	keyboard=[["✍️ Sign up", "🔑 Login"]],
	resize_keyboard=True,
	is_persistent=True,
	one_time_keyboard=True,
	input_field_placeholder="Sign up or log in to get started",
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
	keyboard=[["❌ Cancel"]],
	resize_keyboard=True,
	is_persistent=True,
	one_time_keyboard=True,
)


def inline_confirm_cancel(confirm_text: str, confirm_data: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[[
			InlineKeyboardButton(confirm_text, callback_data=confirm_data),
			InlineKeyboardButton("Cancel", callback_data="cancel"),
		]]
	)


def inline_approve_reject(suggestion_id: str) -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		[[
			InlineKeyboardButton("✅ Approve", callback_data=f"approve:{suggestion_id}"),
			InlineKeyboardButton("❌ Reject", callback_data=f"reject:{suggestion_id}"),
		]]
	)

