from contextlib import asynccontextmanager

from app.application.graph.disambiguation import EntityDisambiguator
from app.application.graph.queries import GraphQueryService
from app.application.graph.updates import GraphUpdateService
from app.application.knowledge_service import KnowledgeService
from app.core.config import get_kb_config
from app.infrastructure.graph_store import KuzuGraphStore
from app.infrastructure.health_clients import InfraHealthClient
from app.infrastructure.persistence import KnowledgePersistence

from shared.utils.logger import get_logger

logger = get_logger(__name__)

config = get_kb_config()
persistence = KnowledgePersistence(config)
knowledge_service = KnowledgeService(persistence)
infra_health_client = InfraHealthClient(config, persistence)

# Graph layer (initialised during lifespan startup)
graph_store = KuzuGraphStore(config)
_disambiguator = EntityDisambiguator(config)
graph_query_service = GraphQueryService(config, graph_store)
graph_update_service = GraphUpdateService(config, graph_store, _disambiguator)


@asynccontextmanager
async def lifespan(app):
    logger.info("Knowledge Base starting up")
    await persistence.connect()

    if config.graph_enabled:
        try:
            graph_store.connect()
            logger.info(
                "KuzuGraphStore connected", extra={"db_path": config.graph_db_path}
            )
        except Exception as exc:
            logger.warning(
                "KuzuGraphStore failed to connect — graph features disabled",
                extra={"error": str(exc)},
            )

    logger.info(
        "Knowledge Base config loaded",
        extra={
            "service_name": config.service_name,
            "service_port": config.service_port,
            "qdrant_url": config.qdrant_url,
            "minio_enabled": config.minio_enabled,
            "graph_enabled": config.graph_enabled,
        },
    )
    yield
    await persistence.close()
    if config.graph_enabled:
        try:
            graph_store.close()
        except Exception:
            pass
    logger.info("Knowledge Base shutting down")
