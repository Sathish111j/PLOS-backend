"""Ingest jobs handler 

Flow:
  User taps "📥 Ingest jobs"  → paginated job history (GET /ingest/history)
  User taps a job             → job detail (GET /ingest/{job_id})
  User taps "🔄 Refresh"      → re-fetches the same job (polling)
  User taps "🔙 Back"         → returns to main menu

Status emoji map:
  pending    → ⏳
  processing → ⚙️
  completed  → ✅
  failed     → ❌
  unknown    → 🔵
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

JOBS_LIST = 40
JOB_DETAIL = 41

PAGE_SIZE = 7

STATUS_EMOJI = {
	"pending": "⏳",
	"processing": "⚙️",
	"running": "⚙️",
	"completed": "✅",
	"done": "✅",
	"failed": "❌",
	"error": "❌",
}

IN_PROGRESS = {"pending", "processing", "running"}


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


def _jobs_kb(jobs: list[dict], page: int) -> InlineKeyboardMarkup:
	start = page * PAGE_SIZE
	slice_ = jobs[start : start + PAGE_SIZE]
	rows = []

	for job in slice_:
		job_id = str(job.get("job_id") or job.get("id") or "")
		status = (job.get("status") or "unknown").lower()
		emoji = STATUS_EMOJI.get(status, "🔵")
		title = job.get("title") or job.get("filename") or job.get("source") or job_id or "Untitled"
		rows.append([InlineKeyboardButton(f"{emoji} {title[:46]}", callback_data=f"jb:detail:{job_id}:{page}")])

	nav = []
	if page > 0:
		nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"jb:list:{page - 1}"))
	if start + PAGE_SIZE < len(jobs):
		nav.append(InlineKeyboardButton("Next ▶", callback_data=f"jb:list:{page + 1}"))
	if nav:
		rows.append(nav)

	rows.append([
		InlineKeyboardButton("🔄 Refresh list", callback_data="jb:reload"),
		InlineKeyboardButton("🔙 Back", callback_data="jb:menu"),
	])
	return InlineKeyboardMarkup(rows)


def _detail_kb(job_id: str, status: str, list_page: int) -> InlineKeyboardMarkup:
	rows = []
	if status in IN_PROGRESS:
		rows.append([InlineKeyboardButton("🔄 Refresh status", callback_data=f"jb:refresh:{job_id}:{list_page}")])
	rows.append([InlineKeyboardButton("◀ Back to jobs", callback_data=f"jb:list:{list_page}")])
	return InlineKeyboardMarkup(rows)


def _fmt_job_list_header(jobs: list[dict]) -> str:
	total = len(jobs)
	completed = sum(1 for j in jobs if (j.get("status") or "").lower() in {"completed", "done"})
	failed = sum(1 for j in jobs if (j.get("status") or "").lower() in {"failed", "error"})
	running = sum(1 for j in jobs if (j.get("status") or "").lower() in IN_PROGRESS)

	parts = [f"📥 *Ingest jobs* ({total} total)"]
	if running:
		parts.append(f"⚙️ {running} running")
	if completed:
		parts.append(f"✅ {completed} completed")
	if failed:
		parts.append(f"❌ {failed} failed")
	return "   ".join(parts)


def _fmt_job_detail(job: dict) -> str:
	job_id = job.get("job_id") or job.get("id") or "—"
	status = (job.get("status") or "unknown").lower()
	emoji = STATUS_EMOJI.get(status, "🔵")
	title = job.get("title") or job.get("filename") or job.get("source") or "—"
	stype = job.get("source_type") or job.get("type") or "—"
	bucket = job.get("bucket_name") or job.get("bucket") or "—"
	created = (job.get("created_at") or "")[:19].replace("T", " ")
	updated = (job.get("updated_at") or "")[:19].replace("T", " ")
	error = job.get("error") or job.get("error_message") or ""
	progress = job.get("progress")

	lines = [
		f"{emoji} *{title}*",
		f"Status: `{status}`",
		f"Job ID: `{job_id}`",
		f"Type: {stype}",
		f"Bucket: {bucket}",
	]
	if created:
		lines.append(f"Started: {created}")
	if updated and updated != created:
		lines.append(f"Updated: {updated}")
	if progress is not None:
		lines.append(f"Progress: {int(progress)}%")
	if error:
		lines.append(f"\n⚠️ Error: _{error[:200]}_")

	return "\n".join(lines)


async def jobs_entry(update: Update, context: CallbackContext) -> int:
	jwt = await _jwt(update)
	if not jwt or update.effective_chat is None or update.effective_message is None:
		return ConversationHandler.END

	await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

	try:
		data = await api.get_ingest_history(jwt)
	except APIError as exc:
		if exc.status == 401 and update.effective_user is not None:
			await session.delete_jwt(update.effective_user.id)
		await update.effective_message.reply_text(f"Could not load jobs: {exc.detail}", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	jobs = data.get("jobs") or data.get("history") or data.get("items") or (data if isinstance(data, list) else [])
	context.user_data["jb_jobs"] = jobs

	if not jobs:
		await update.effective_message.reply_text(
			"No ingest jobs yet. Send me a file, link, or text to get started.",
			reply_markup=MAIN_MENU,
		)
		return ConversationHandler.END

	await update.effective_message.reply_text(
		_fmt_job_list_header(jobs),
		parse_mode=ParseMode.MARKDOWN,
		reply_markup=_jobs_kb(jobs, page=0),
	)
	return JOBS_LIST


async def jobs_callback(update: Update, context: CallbackContext) -> int:
	cq = update.callback_query
	if cq is None or update.effective_user is None or update.effective_chat is None:
		return ConversationHandler.END
	await cq.answer()
	jwt = await session.get_jwt(update.effective_user.id)

	if not jwt:
		await cq.edit_message_text("Session expired. Tap /start to log in again.")
		return ConversationHandler.END

	data = cq.data or ""
	jobs = context.user_data.get("jb_jobs", [])

	if data == "jb:menu":
		await cq.edit_message_text("Returning to main menu.")
		await context.bot.send_message(update.effective_chat.id, "What would you like to do?", reply_markup=MAIN_MENU)
		return ConversationHandler.END

	if data == "jb:reload":
		await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			fresh = await api.get_ingest_history(jwt)
		except APIError as exc:
			await cq.answer(f"Refresh failed: {exc.detail}", show_alert=True)
			return JOBS_LIST

		jobs = fresh.get("jobs") or fresh.get("history") or fresh.get("items") or (fresh if isinstance(fresh, list) else [])
		context.user_data["jb_jobs"] = jobs
		await cq.edit_message_text(_fmt_job_list_header(jobs), parse_mode=ParseMode.MARKDOWN, reply_markup=_jobs_kb(jobs, page=0))
		return JOBS_LIST

	if data.startswith("jb:list:"):
		page = int(data.split(":")[-1])
		await cq.edit_message_text(_fmt_job_list_header(jobs), parse_mode=ParseMode.MARKDOWN, reply_markup=_jobs_kb(jobs, page))
		return JOBS_LIST

	if data.startswith("jb:detail:"):
		parts = data.split(":")
		job_id = parts[2]
		list_page = int(parts[3])

		await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			job = await api.get_ingest_job(jwt, job_id)
		except APIError as exc:
			job = next((j for j in jobs if str(j.get("job_id") or j.get("id")) == job_id), None)
			if not job:
				await cq.edit_message_text(f"Could not load job: {exc.detail}")
				return JOBS_LIST

		status = (job.get("status") or "unknown").lower()
		context.user_data["jb_current_job"] = job

		await cq.edit_message_text(_fmt_job_detail(job), parse_mode=ParseMode.MARKDOWN, reply_markup=_detail_kb(job_id, status, list_page))
		return JOB_DETAIL

	if data.startswith("jb:refresh:"):
		parts = data.split(":")
		job_id = parts[2]
		list_page = int(parts[3])

		await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
		try:
			job = await api.get_ingest_job(jwt, job_id)
		except APIError as exc:
			await cq.answer(f"Refresh failed: {exc.detail}", show_alert=True)
			return JOB_DETAIL

		status = (job.get("status") or "unknown").lower()
		context.user_data["jb_current_job"] = job

		for i, j in enumerate(jobs):
			if str(j.get("job_id") or j.get("id")) == job_id:
				jobs[i] = job
				break
		context.user_data["jb_jobs"] = jobs

		await cq.edit_message_text(_fmt_job_detail(job), parse_mode=ParseMode.MARKDOWN, reply_markup=_detail_kb(job_id, status, list_page))
		return JOB_DETAIL

	return JOBS_LIST


async def jobs_back(update: Update, context: CallbackContext) -> int:
	context.user_data.pop("jb_jobs", None)
	context.user_data.pop("jb_current_job", None)
	if update.effective_message:
		await update.effective_message.reply_text("Back to main menu.", reply_markup=MAIN_MENU)
	return ConversationHandler.END


def build_jobs_handler() -> ConversationHandler:
	back_filter = filters.Regex(r"^🔙 Back$")

	return ConversationHandler(
		entry_points=[
			MessageHandler(filters.Regex(r"^(📥 Ingest jobs|📋 Jobs)$"), jobs_entry),
		],
		states={
			JOBS_LIST: [CallbackQueryHandler(jobs_callback, pattern=r"^jb:"), MessageHandler(back_filter, jobs_back)],
			JOB_DETAIL: [CallbackQueryHandler(jobs_callback, pattern=r"^jb:"), MessageHandler(back_filter, jobs_back)],
		},
		fallbacks=[MessageHandler(back_filter, jobs_back)],
		persistent=True,
		name="jobs_conversation",
	)