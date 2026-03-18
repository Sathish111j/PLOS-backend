"""Async HTTP client for the backend API.

All methods raise APIError on non-2xx responses so handlers
can catch a single exception type.
"""

from __future__ import annotations

import logging
from base64 import b64encode
from dataclasses import dataclass
from typing import Any

import httpx

from bot.config import API_BASE_URL

log = logging.getLogger(__name__)


@dataclass
class APIError(Exception):
	status: int
	detail: str

	def __str__(self) -> str:
		return f"API {self.status}: {self.detail}"


def _headers(jwt: str | None = None) -> dict[str, str]:
	headers = {"Content-Type": "application/json"}
	if jwt:
		headers["Authorization"] = f"Bearer {jwt}"
	return headers


async def _raise_for(resp: httpx.Response) -> None:
	if resp.is_success:
		return
	try:
		payload = resp.json()
		detail = payload.get("detail", resp.text) if isinstance(payload, dict) else resp.text
	except Exception:
		detail = resp.text
	raise APIError(status=resp.status_code, detail=str(detail))


async def _request(
	method: str,
	path: str,
	*,
	jwt: str | None = None,
	json: dict[str, Any] | None = None,
	params: dict[str, Any] | None = None,
	timeout: float = 30.0,
) -> dict[str, Any]:
	async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=timeout) as client:
		resp = await client.request(
			method,
			path,
			json=json,
			params=params,
			headers=_headers(jwt),
		)
	await _raise_for(resp)
	data = resp.json()
	if not isinstance(data, dict):
		raise APIError(status=resp.status_code, detail="Unexpected response format")
	return data


# ── Auth ──────────────────────────────────────────────────────────────────────


async def register(
	email: str,
	username: str,
	password: str,
	full_name: str = "",
) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"email": email,
		"username": username,
		"password": password,
	}
	if full_name:
		payload["full_name"] = full_name
	return await _request("POST", "/auth/register", json=payload, timeout=15)


async def login(email: str, password: str) -> dict[str, Any]:
	return await _request(
		"POST",
		"/auth/login",
		json={"email": email, "password": password},
		timeout=15,
	)


async def get_me(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/auth/me", jwt=jwt, timeout=15)


async def change_password(
	jwt: str,
	current_password: str,
	new_password: str,
) -> dict[str, Any]:
	return await _request(
		"POST",
		"/auth/change-password",
		jwt=jwt,
		json={"current_password": current_password, "new_password": new_password},
		timeout=15,
	)


async def verify_token(jwt: str) -> dict[str, Any]:
	return await _request("POST", "/auth/verify-token", jwt=jwt, timeout=15)


# ── Knowledge base ────────────────────────────────────────────────────────────


async def upload_document(
	jwt: str,
	filename: str,
	*,
	content_base64: str | None = None,
	mime_type: str | None = None,
	source_url: str | None = None,
	bucket_id: str | None = None,
	bucket_hint: str | None = None,
) -> dict[str, Any]:
	payload: dict[str, Any] = {"filename": filename}
	if content_base64 is not None:
		payload["content_base64"] = content_base64
	if mime_type is not None:
		payload["mime_type"] = mime_type
	if source_url is not None:
		payload["source_url"] = source_url
	if bucket_id is not None:
		payload["bucket_id"] = bucket_id
	if bucket_hint is not None:
		payload["bucket_hint"] = bucket_hint
	return await _request("POST", "/upload", jwt=jwt, json=payload, timeout=60)


async def ingest_document(
	jwt: str,
	filename: str,
	*,
	content_base64: str | None = None,
	mime_type: str | None = None,
	source_url: str | None = None,
	bucket_id: str | None = None,
	bucket_hint: str | None = None,
) -> dict[str, Any]:
	payload: dict[str, Any] = {"filename": filename}
	if content_base64 is not None:
		payload["content_base64"] = content_base64
	if mime_type is not None:
		payload["mime_type"] = mime_type
	if source_url is not None:
		payload["source_url"] = source_url
	if bucket_id is not None:
		payload["bucket_id"] = bucket_id
	if bucket_hint is not None:
		payload["bucket_hint"] = bucket_hint
	return await _request("POST", "/ingest", jwt=jwt, json=payload, timeout=60)


async def chat(jwt: str, message: str, session_id: str | None = None) -> dict[str, Any]:
	payload: dict[str, Any] = {"message": message}
	if session_id:
		payload["session_id"] = session_id
	return await _request("POST", "/chat", jwt=jwt, json=payload, timeout=60)


async def search(
	jwt: str,
	query: str,
	*,
	top_k: int = 10,
	latency_budget_ms: int = 100,
	bucket_id: str | None = None,
	content_type: str | None = None,
	tags: list[str] | None = None,
	created_after: str | None = None,
	created_before: str | None = None,
	enable_rerank: bool = True,
) -> dict[str, Any]:
	payload: dict[str, Any] = {
		"query": query,
		"top_k": top_k,
		"latency_budget_ms": latency_budget_ms,
		"enable_rerank": enable_rerank,
	}
	if bucket_id is not None:
		payload["bucket_id"] = bucket_id
	if content_type is not None:
		payload["content_type"] = content_type
	if tags is not None:
		payload["tags"] = tags
	if created_after is not None:
		payload["created_after"] = created_after
	if created_before is not None:
		payload["created_before"] = created_before
	return await _request("POST", "/search", jwt=jwt, json=payload, timeout=30)


async def list_documents(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/documents", jwt=jwt, timeout=15)


async def get_buckets(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/buckets", jwt=jwt, timeout=15)


async def get_bucket_tree(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/buckets/tree", jwt=jwt, timeout=15)


async def get_bucket_items(jwt: str, bucket_id: str, *, offset: int = 0, limit: int = 50) -> dict[str, Any]:
	return await _request(
		"GET",
		f"/buckets/{bucket_id}/items",
		jwt=jwt,
		params={"offset": offset, "limit": limit},
		timeout=15,
	)


async def upload_file(
	jwt: str,
	filename: str,
	content: bytes,
	mime: str,
) -> dict[str, Any]:
	return await upload_document(
		jwt,
		filename,
		content_base64=b64encode(content).decode("utf-8"),
		mime_type=mime,
	)


async def ingest(jwt: str, payload: dict[str, Any]) -> dict[str, Any]:
	return await _request("POST", "/ingest", jwt=jwt, json=payload, timeout=60)


async def create_bucket(jwt: str, payload: dict[str, Any]) -> dict[str, Any]:
	return await _request("POST", "/buckets", jwt=jwt, json=payload, timeout=15)


async def update_bucket(jwt: str, bucket_id: str, payload: dict[str, Any]) -> dict[str, Any]:
	return await _request("PATCH", f"/buckets/{bucket_id}", jwt=jwt, json=payload, timeout=15)


async def get_item(jwt: str, item_id: str) -> dict[str, Any]:
	return await _request("GET", f"/items/{item_id}", jwt=jwt, timeout=15)


async def move_item(jwt: str, item_id: str, bucket_id: str) -> dict[str, Any]:
	return await _request(
		"PATCH",
		f"/items/{item_id}/move",
		jwt=jwt,
		json={"bucket_id": bucket_id},
		timeout=15,
	)


async def delete_item(jwt: str, item_id: str) -> dict[str, Any]:
	return await _request("DELETE", f"/items/{item_id}", jwt=jwt, timeout=15)


async def move_bucket(jwt: str, bucket_id: str, parent_bucket_id: str | None = None) -> dict[str, Any]:
	return await _request(
		"POST",
		f"/buckets/{bucket_id}/move",
		jwt=jwt,
		json={"parent_bucket_id": parent_bucket_id},
		timeout=15,
	)


async def delete_bucket(
	jwt: str,
	bucket_id: str,
	target_bucket_id: str | None = None,
) -> dict[str, Any]:
	return await _request(
		"DELETE",
		f"/buckets/{bucket_id}",
		jwt=jwt,
		json={"target_bucket_id": target_bucket_id},
		timeout=15,
	)


async def bulk_move_documents(
	jwt: str,
	source_bucket_id: str,
	target_bucket_id: str,
) -> dict[str, Any]:
	return await _request(
		"POST",
		"/buckets/bulk-move-documents",
		jwt=jwt,
		json={
			"source_bucket_id": source_bucket_id,
			"target_bucket_id": target_bucket_id,
		},
		timeout=30,
	)


async def route_bucket_preview(
	jwt: str,
	title: str,
	preview_text: str,
	bucket_hint: str | None = None,
) -> dict[str, Any]:
	payload: dict[str, Any] = {"title": title, "preview_text": preview_text}
	if bucket_hint is not None:
		payload["bucket_hint"] = bucket_hint
	return await _request("POST", "/buckets/route-preview", jwt=jwt, json=payload, timeout=30)


async def get_ingest_history(jwt: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
	return await _request(
		"GET",
		"/ingest/history",
		jwt=jwt,
		params={"offset": offset, "limit": limit},
		timeout=15,
	)


async def get_ingest_job(jwt: str, job_id: str) -> dict[str, Any]:
	return await _request("GET", f"/ingest/{job_id}", jwt=jwt, timeout=15)


async def get_suggestions(
	jwt: str,
	status: str = "pending",
	offset: int = 0,
	limit: int = 50,
) -> dict[str, Any]:
	return await _request(
		"GET",
		"/suggestions",
		jwt=jwt,
		params={"status": status, "offset": offset, "limit": limit},
		timeout=15,
	)


async def get_suggestion_history(jwt: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
	return await _request(
		"GET",
		"/suggestions/history",
		jwt=jwt,
		params={"offset": offset, "limit": limit},
		timeout=15,
	)


async def approve_suggestion(
	jwt: str,
	suggestion_id: str,
	name: str | None = None,
	description: str | None = None,
) -> dict[str, Any]:
	payload: dict[str, Any] = {}
	if name is not None:
		payload["name"] = name
	if description is not None:
		payload["description"] = description
	return await _request(
		"POST",
		f"/suggestions/{suggestion_id}/approve",
		jwt=jwt,
		json=payload,
		timeout=15,
	)


async def reject_suggestion(jwt: str, suggestion_id: str, *, comment: str | None = None) -> dict[str, Any]:
	payload: dict[str, Any] = {}
	if comment:
		payload["comment"] = comment
	return await _request(
		"POST",
		f"/suggestions/{suggestion_id}/reject",
		jwt=jwt,
		json=payload or None,
		timeout=15,
	)


async def get_settings(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/settings", jwt=jwt, timeout=15)


async def update_settings(jwt: str, payload: dict[str, Any]) -> dict[str, Any]:
	return await _request("PATCH", "/settings", jwt=jwt, json=payload, timeout=15)


async def get_chat_sessions(
	jwt: str,
	*,
	limit: int = 50,
	offset: int = 0,
	include_archived: bool = False,
) -> dict[str, Any]:
	return await _request(
		"GET",
		"/chat/sessions",
		jwt=jwt,
		params={
			"limit": limit,
			"offset": offset,
			"include_archived": include_archived,
		},
		timeout=15,
	)


async def get_chat_session(jwt: str, session_id: str, limit: int = 100) -> dict[str, Any]:
	return await _request(
		"GET",
		f"/chat/sessions/{session_id}",
		jwt=jwt,
		params={"limit": limit},
		timeout=15,
	)


async def delete_chat_session(jwt: str, session_id: str) -> dict[str, Any]:
	return await _request("DELETE", f"/chat/sessions/{session_id}", jwt=jwt, timeout=15)


async def get_embedding_dlq_stats(jwt: str) -> dict[str, Any]:
	return await _request("GET", "/ops/embedding-dlq/stats", jwt=jwt, timeout=15)


async def reprocess_embedding_dlq_unreplayable(
	jwt: str,
	*,
	max_items: int = 100,
	purge_unrecoverable: bool = False,
	trigger_replay_cycle: bool = True,
) -> dict[str, Any]:
	return await _request(
		"POST",
		"/ops/embedding-dlq/reprocess-unreplayable",
		jwt=jwt,
		json={
			"max_items": max_items,
			"purge_unrecoverable": purge_unrecoverable,
			"trigger_replay_cycle": trigger_replay_cycle,
		},
		timeout=60,
	)


async def purge_embedding_dlq_unreplayable(
	jwt: str,
	*,
	max_items: int = 100,
) -> dict[str, Any]:
	return await _request(
		"POST",
		"/ops/embedding-dlq/purge-unreplayable",
		jwt=jwt,
		json={"max_items": max_items},
		timeout=60,
	)
