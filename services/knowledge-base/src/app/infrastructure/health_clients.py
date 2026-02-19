from typing import Dict

import httpx
from app.core.config import KnowledgeBaseConfig
from app.infrastructure.persistence import KnowledgePersistence


class InfraHealthClient:
    def __init__(self, config: KnowledgeBaseConfig, persistence: KnowledgePersistence):
        self.config = config
        self.persistence = persistence

    async def check_qdrant(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.config.qdrant_url}/healthz")
            return "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            return "unreachable"

    async def check_minio(self) -> str:
        if not self.config.minio_enabled:
            return "disabled"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(self.config.minio_health_url)
            return "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            return "unreachable"

    async def check_dependencies(self) -> Dict[str, str]:
        qdrant_status = await self.check_qdrant()
        minio_status = await self.check_minio()
        postgres_status = await self.persistence.check_postgres()
        meilisearch_status = await self.persistence.check_meilisearch()
        return {
            "qdrant": qdrant_status,
            "minio": minio_status,
            "postgres": postgres_status,
            "meilisearch": meilisearch_status,
        }
