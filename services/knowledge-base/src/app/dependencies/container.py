from contextlib import asynccontextmanager

from app.application.knowledge_service import KnowledgeService
from app.core.config import get_kb_config
from app.infrastructure.health_clients import InfraHealthClient
from app.infrastructure.persistence import KnowledgePersistence

from shared.utils.logger import get_logger

logger = get_logger(__name__)

config = get_kb_config()
persistence = KnowledgePersistence(config)
knowledge_service = KnowledgeService(persistence)
infra_health_client = InfraHealthClient(config, persistence)


@asynccontextmanager
async def lifespan(app):
    logger.info("Knowledge Base starting up")
    await persistence.connect()
    logger.info(
        "Knowledge Base config loaded",
        extra={
            "service_name": config.service_name,
            "service_port": config.service_port,
            "qdrant_url": config.qdrant_url,
            "minio_enabled": config.minio_enabled,
        },
    )
    yield
    await persistence.close()
    logger.info("Knowledge Base shutting down")
