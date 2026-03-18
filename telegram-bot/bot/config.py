"""Environment-backed configuration for the Telegram bot."""

from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


API_BASE_URL = os.getenv("API_BASE_URL", "http://api-gateway:8000/api/v1")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
JWT_TTL = int(os.getenv("JWT_TTL", "3600"))
