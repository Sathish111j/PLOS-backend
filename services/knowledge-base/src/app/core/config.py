import os
from dataclasses import dataclass
from functools import lru_cache

from shared.utils.unified_config import get_unified_settings


@dataclass(frozen=True)
class KnowledgeBaseConfig:
    service_name: str
    service_port: int
    log_level: str
    app_env: str
    debug: bool
    qdrant_url: str
    qdrant_collection: str
    minio_enabled: bool
    minio_endpoint: str
    minio_secure: bool
    minio_bucket: str
    minio_access_key: str
    minio_secret_key: str
    database_url: str

    @property
    def minio_health_url(self) -> str:
        protocol = "https" if self.minio_secure else "http"
        endpoint = self.minio_endpoint.replace("http://", "").replace("https://", "")
        return f"{protocol}://{endpoint}/minio/health/live"


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache()
def get_kb_config() -> KnowledgeBaseConfig:
    unified = get_unified_settings()
    return KnowledgeBaseConfig(
        service_name=os.getenv("SERVICE_NAME", "knowledge-base"),
        service_port=int(os.getenv("PORT", str(unified.service_port))),
        log_level=os.getenv("LOG_LEVEL", unified.log_level),
        app_env=os.getenv("APP_ENV", unified.app_env),
        debug=_parse_bool(os.getenv("DEBUG"), unified.debug),
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "documents"),
        minio_enabled=_parse_bool(os.getenv("MINIO_ENABLED"), True),
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "minio:9000"),
        minio_secure=_parse_bool(os.getenv("MINIO_SECURE"), False),
        minio_bucket=os.getenv("MINIO_BUCKET", "knowledge-base-documents"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "plos_minio_admin"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY", "plos_minio_secure_2026"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:plos_db_secure_2025@supabase-db:5432/plos",
        ),
    )
