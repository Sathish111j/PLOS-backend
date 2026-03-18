"""Redis-backed session store.

Keys used:
  jwt:{tg_user_id}       → JWT string, TTL = JWT_TTL
  ctx:{tg_user_id}       → JSON blob of per-user context (chat session_id, etc.)
"""

from __future__ import annotations

# pyright: reportMissingImports=false

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from bot.config import JWT_TTL, REDIS_URL

log = logging.getLogger(__name__)

# Module-level client — initialised once in main.py via init()
_redis: aioredis.Redis | None = None


async def init() -> None:
	global _redis
	if _redis is None:
		client = aioredis.from_url(REDIS_URL, decode_responses=True)
		await client.ping()
		_redis = client
	else:
		await _redis.ping()
	log.info("Redis connected: %s", REDIS_URL)


async def close() -> None:
	global _redis
	if _redis is not None:
		await _redis.aclose()
		_redis = None


def _ensure_redis() -> aioredis.Redis:
	if _redis is None:
		raise RuntimeError("Redis is not initialised. Call session.init() first.")
	return _redis


def _jwt_key(tg_user_id: int) -> str:
	return f"jwt:{tg_user_id}"


def _ctx_key(tg_user_id: int) -> str:
	return f"ctx:{tg_user_id}"


# ── JWT ──────────────────────────────────────────────────────────────────────


async def set_jwt(tg_user_id: int, jwt: str) -> None:
	"""Store JWT with TTL. Overwrites any existing token."""
	await _ensure_redis().set(_jwt_key(tg_user_id), jwt, ex=JWT_TTL)


async def get_jwt(tg_user_id: int) -> str | None:
	"""Return JWT string or None if missing / expired."""
	return await _ensure_redis().get(_jwt_key(tg_user_id))


async def delete_jwt(tg_user_id: int) -> None:
	"""Clear JWT and context on logout."""
	await _ensure_redis().delete(_jwt_key(tg_user_id), _ctx_key(tg_user_id))


async def is_authenticated(tg_user_id: int) -> bool:
	return await get_jwt(tg_user_id) is not None


# ── Per-user context (chat session_id, current bucket, etc.) ─────────────────


async def set_ctx(tg_user_id: int, key: str, value: Any) -> None:
	"""Set a single key inside the user's context blob."""
	raw = await _ensure_redis().get(_ctx_key(tg_user_id))
	ctx: dict[str, Any] = json.loads(raw) if raw else {}
	ctx[key] = value
	await _ensure_redis().set(_ctx_key(tg_user_id), json.dumps(ctx), ex=JWT_TTL)


async def get_ctx(tg_user_id: int, key: str, default: Any = None) -> Any:
	"""Get a single key from the user's context blob."""
	raw = await _ensure_redis().get(_ctx_key(tg_user_id))
	if not raw:
		return default
	return json.loads(raw).get(key, default)


async def clear_ctx_key(tg_user_id: int, key: str) -> None:
	raw = await _ensure_redis().get(_ctx_key(tg_user_id))
	if not raw:
		return
	ctx = json.loads(raw)
	ctx.pop(key, None)
	await _ensure_redis().set(_ctx_key(tg_user_id), json.dumps(ctx), ex=JWT_TTL)

