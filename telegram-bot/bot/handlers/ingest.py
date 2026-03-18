"""Ingest handler 

Every message a logged-in user sends is automatically ingested.

Routing logic:

  Text only          → extract URLs if any, POST /ingest as text
  Text + media       → ingest both the caption text AND the file
  Document (any)     → download → POST /ingest
  Photo              → download highest-res → POST /ingest
  Voice              → download .ogg → POST /ingest
  Audio              → download → POST /ingest
  Video              → download → POST /ingest
  URL in text        → POST /ingest with source_url field

All handlers check for a valid JWT first. If not authenticated,
the user is redirected to /start.
"""

# pyright: reportMissingImports=false

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from io import BytesIO

from telegram import Update
from telegram.ext import CallbackContext, ContextTypes, MessageHandler, filters

import bot.api_client as api
from bot import session
from bot.api_client import APIError
from bot.keyboards.main_menu import MAIN_MENU, WELCOME_KEYBOARD

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s]+")

JOB_STATUS_EMOJI = {
	"pending": "⏳",
	"processing": "⚙️",
	"completed": "✅",
	"failed": "❌",
}


async def _get_jwt_or_redirect(update: Update) -> str | None:
	uid = update.effective_user.id if update.effective_user else None
	if uid is None:
		return None
	jwt = await session.get_jwt(uid)
	if not jwt and update.effective_message:
		await update.effective_message.reply_text(
			"You're not logged in. Tap /start to sign in.",
			reply_markup=WELCOME_KEYBOARD,
		)
	return jwt


async def _reply_job(update: Update, result: dict, label: str) -> None:
	job_id = result.get("job_id") or result.get("id", "—")
	status = result.get("status", "pending")
	emoji = JOB_STATUS_EMOJI.get(status, "📥")
	bucket = result.get("bucket_name") or result.get("bucket", "")

	lines = [f"{emoji} {label} queued for ingestion"]
	if job_id and job_id != "—":
		lines.append(f"Job ID: `{job_id}`")
	if bucket:
		lines.append(f"Bucket: {bucket}")
	lines.append("Use *Jobs* from the menu to check progress.")

	if update.effective_message:
		await update.effective_message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=MAIN_MENU)


async def _reply_error(update: Update, label: str, exc: APIError) -> None:
	log.warning("ingest failed (%s): %s", label, exc)
	msg = "Session expired — please /start to log in again." if exc.status == 401 else f"Could not ingest {label}: {exc.detail}"
	if exc.status == 401 and update.effective_user is not None:
		await session.delete_jwt(update.effective_user.id)
	if update.effective_message:
		await update.effective_message.reply_text(msg, reply_markup=MAIN_MENU)


async def _download(context: ContextTypes.DEFAULT_TYPE, file_id: str) -> bytes:
	tg_file = await context.bot.get_file(file_id)
	buf = BytesIO()
	await tg_file.download_to_memory(buf)
	return buf.getvalue()


def _payload_from_text(text: str) -> dict[str, str]:
	return {
		"filename": "note.txt",
		"content_base64": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
		"mime_type": "text/plain",
	}


async def handle_text(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None:
		return

	text = (update.effective_message.text or "").strip()
	if not text:
		await update.effective_message.reply_text("Nothing to ingest — message was empty.", reply_markup=MAIN_MENU)
		return

	urls = URL_RE.findall(text)
	text_without_urls = URL_RE.sub("", text).strip()
	ingested_anything = False

	for url in urls:
		try:
			result = await api.ingest(jwt, {
				"filename": url,
				"source_url": url,
				"mime_type": "text/uri-list",
			})
			await _reply_job(update, result, f"URL: {url[:60]}")
			ingested_anything = True
		except APIError as exc:
			await _reply_error(update, "URL", exc)
			return

	if text_without_urls:
		try:
			result = await api.ingest(jwt, _payload_from_text(text_without_urls))
			await _reply_job(update, result, "Note")
			ingested_anything = True
		except APIError as exc:
			await _reply_error(update, "note", exc)
			return

	if not ingested_anything:
		await update.effective_message.reply_text(
			"Nothing to ingest — message was empty after parsing.",
			reply_markup=MAIN_MENU,
		)


async def handle_document(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None or update.effective_message.document is None:
		return

	doc = update.effective_message.document
	filename = doc.file_name or f"document_{doc.file_unique_id}"
	mime = doc.mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
	caption = (update.effective_message.caption or "").strip()

	await update.effective_message.reply_text(f"📎 Downloading {filename}…")

	try:
		raw = await _download(context, doc.file_id)
		result = await api.ingest(
			jwt,
			{
				"filename": filename,
				"content_base64": base64.b64encode(raw).decode("utf-8"),
				"mime_type": mime,
			},
		)
		await _reply_job(update, result, filename)
	except Exception as exc:
		log.error("document ingest failed: %s", exc)
		if isinstance(exc, APIError):
			await _reply_error(update, filename, exc)
		else:
			await update.effective_message.reply_text("Download failed — try again.")
		return

	if caption:
		try:
			result = await api.ingest(jwt, _payload_from_text(caption))
			await _reply_job(update, result, "Caption note")
		except APIError as exc:
			await _reply_error(update, "caption", exc)


async def handle_photo(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None or not update.effective_message.photo:
		return

	photo = update.effective_message.photo[-1]
	filename = f"photo_{photo.file_unique_id}.jpg"
	caption = (update.effective_message.caption or "").strip()

	await update.effective_message.reply_text("🖼 Downloading photo…")

	try:
		raw = await _download(context, photo.file_id)
		result = await api.ingest(
			jwt,
			{
				"filename": filename,
				"content_base64": base64.b64encode(raw).decode("utf-8"),
				"mime_type": "image/jpeg",
			},
		)
		await _reply_job(update, result, "Photo")
	except APIError as exc:
		await _reply_error(update, "photo", exc)
		return
	except Exception as exc:
		log.error("photo download failed: %s", exc)
		await update.effective_message.reply_text("Download failed — try again.")
		return

	if caption:
		try:
			result = await api.ingest(jwt, _payload_from_text(caption))
			await _reply_job(update, result, "Photo caption")
		except APIError as exc:
			await _reply_error(update, "caption", exc)


async def handle_voice(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None or update.effective_message.voice is None:
		return

	voice = update.effective_message.voice
	filename = f"voice_{voice.file_unique_id}.ogg"
	duration = voice.duration or 0

	await update.effective_message.reply_text(f"🎙 Downloading voice message ({duration}s)…")

	try:
		raw = await _download(context, voice.file_id)
		result = await api.ingest(
			jwt,
			{
				"filename": filename,
				"content_base64": base64.b64encode(raw).decode("utf-8"),
				"mime_type": "audio/ogg",
			},
		)
		await _reply_job(update, result, "Voice message")
	except APIError as exc:
		await _reply_error(update, "voice message", exc)
	except Exception as exc:
		log.error("voice download failed: %s", exc)
		await update.effective_message.reply_text("Download failed — try again.")


async def handle_audio(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None or update.effective_message.audio is None:
		return

	audio = update.effective_message.audio
	filename = audio.file_name or f"audio_{audio.file_unique_id}.mp3"
	mime = audio.mime_type or "audio/mpeg"
	title = audio.title or filename
	caption = (update.effective_message.caption or "").strip()

	await update.effective_message.reply_text(f"🎵 Downloading {title}…")

	try:
		raw = await _download(context, audio.file_id)
		result = await api.ingest(
			jwt,
			{
				"filename": filename,
				"content_base64": base64.b64encode(raw).decode("utf-8"),
				"mime_type": mime,
			},
		)
		await _reply_job(update, result, title)
	except APIError as exc:
		await _reply_error(update, "audio", exc)
	except Exception as exc:
		log.error("audio download failed: %s", exc)
		await update.effective_message.reply_text("Download failed — try again.")
		return

	if caption:
		try:
			result = await api.ingest(jwt, _payload_from_text(caption))
			await _reply_job(update, result, "Audio caption")
		except APIError as exc:
			await _reply_error(update, "caption", exc)


async def handle_video(update: Update, context: CallbackContext) -> None:
	jwt = await _get_jwt_or_redirect(update)
	if not jwt or update.effective_message is None or update.effective_message.video is None:
		return

	video = update.effective_message.video
	filename = video.file_name or f"video_{video.file_unique_id}.mp4"
	mime = video.mime_type or "video/mp4"
	caption = (update.effective_message.caption or "").strip()

	await update.effective_message.reply_text(f"🎬 Downloading {filename}…")

	try:
		raw = await _download(context, video.file_id)
		result = await api.ingest(
			jwt,
			{
				"filename": filename,
				"content_base64": base64.b64encode(raw).decode("utf-8"),
				"mime_type": mime,
			},
		)
		await _reply_job(update, result, filename)
	except APIError as exc:
		await _reply_error(update, "video", exc)
		return
	except Exception as exc:
		log.error("video download failed: %s", exc)
		await update.effective_message.reply_text("Download failed — try again.")
		return

	if caption:
		try:
			result = await api.ingest(jwt, _payload_from_text(caption))
			await _reply_job(update, result, "Video caption")
		except APIError as exc:
			await _reply_error(update, "caption", exc)


def build_ingest_handler() -> list[MessageHandler]:
	menu_buttons = filters.Regex(r"^(💬 Chat|🔍 Search|🗂️? Buckets|💡 Suggestions|🧠 Suggestions|📥 Ingest jobs|📋 Jobs|⚙️ Settings)$")
	return [
		MessageHandler(filters.VOICE, handle_voice),
		MessageHandler(filters.AUDIO, handle_audio),
		MessageHandler(filters.VIDEO, handle_video),
		MessageHandler(filters.PHOTO, handle_photo),
		MessageHandler(filters.Document.ALL, handle_document),
		MessageHandler(filters.TEXT & ~filters.COMMAND & ~menu_buttons, handle_text),
	]