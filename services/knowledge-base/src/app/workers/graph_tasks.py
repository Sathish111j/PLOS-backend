"""
Phase 4 — Celery Graph Worker Tasks.

Tasks:
  graph_extract_document  — main NER + graph construction pipeline.
  graph_delete_document   — remove document and clean orphans.
  graph_update_document   — update content (delete old + re-extract).
  graph_move_bucket       — propagate bucket move to graph.
  graph_run_pagerank      — PageRank background job.
  graph_run_orphan_cleanup — orphan cleanup background job.
  graph_run_health_check  — graph health check.

All tasks share a module-level KuzuGraphStore and EntityDisambiguator
(initialised once per worker process via the 'init_worker' signal handler).
"""

from __future__ import annotations

import asyncio

from celery import Celery
from celery.signals import worker_process_init

from app.application.graph.background import (
    run_health_check,
    run_orphan_cleanup,
    run_pagerank,
)
from app.application.graph.construction import GraphConstructor
from app.application.graph.disambiguation import EntityDisambiguator
from app.application.graph.models import GraphExtractionTask
from app.application.graph.updates import GraphUpdateService
from app.core.config import get_kb_config

from shared.utils.logger import get_logger

logger = get_logger(__name__)

config = get_kb_config()

celery_app = Celery(
    "knowledge_base_graph",
    broker=config.celery_broker_url,
    backend=config.celery_backend_url,
)
celery_app.conf.task_default_queue = config.graph_celery_queue

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    "graph-pagerank-every-6h": {
        "task": "knowledge_base.graph_run_pagerank",
        "schedule": 6 * 3600,
        "kwargs": {"user_id": "all"},
    },
    "graph-orphan-cleanup-every-24h": {
        "task": "knowledge_base.graph_run_orphan_cleanup",
        "schedule": 24 * 3600,
        "kwargs": {"user_id": "all"},
    },
    "graph-health-check-every-15m": {
        "task": "knowledge_base.graph_run_health_check",
        "schedule": 15 * 60,
        "kwargs": {"pg_document_count": 0},
    },
}

# Module-level singletons (lazily initialised in each worker process)
_graph_store = None
_disambiguator = None
_update_service = None


def _get_store():
    global _graph_store
    if _graph_store is None:
        from app.infrastructure.graph_store import KuzuGraphStore

        _graph_store = KuzuGraphStore(config)
        _graph_store.connect()
    return _graph_store


def _get_disambiguator():
    global _disambiguator
    if _disambiguator is None:
        _disambiguator = EntityDisambiguator(config)
    return _disambiguator


def _get_update_service():
    global _update_service
    if _update_service is None:
        _update_service = GraphUpdateService(
            config,
            _get_store(),
            _get_disambiguator(),
        )
    return _update_service


@worker_process_init.connect
def _init_worker(**_kwargs):
    """Pre-warm singletons on worker process start."""
    try:
        _get_store()
        _get_disambiguator()
        logger.info("Graph worker initialised")
    except Exception as exc:
        logger.warning("Graph worker init warning", extra={"error": str(exc)})


# ---------------------------------------------------------------------------
# Task helpers
# ---------------------------------------------------------------------------


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("loop closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@celery_app.task(name="knowledge_base.graph_extract_document", bind=True, max_retries=3)
def graph_extract_document(self, *, payload: dict) -> dict:
    """
    Main graph extraction task.

    Payload keys: document_id, user_id, bucket_id, title, chunks, word_count, source_url.
    """
    task = GraphExtractionTask(
        document_id=payload["document_id"],
        user_id=payload["user_id"],
        bucket_id=payload.get("bucket_id", ""),
        title=payload.get("title", ""),
        chunks=payload.get("chunks", []),
        word_count=payload.get("word_count", 0),
        source_url=payload.get("source_url", ""),
    )

    store = _get_store()
    disambiguator = _get_disambiguator()
    constructor = GraphConstructor(config, store)

    try:
        return _run_async(constructor.process_document(task, disambiguator))
    except Exception as exc:
        logger.error(
            "Graph extraction failed",
            extra={"document_id": task.document_id, "error": str(exc)},
        )
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="knowledge_base.graph_delete_document")
def graph_delete_document(*, document_id: str, user_id: str) -> dict:
    """Remove a document and clean orphans from the graph."""
    svc = _get_update_service()
    return svc.delete_document(document_id, user_id)


@celery_app.task(name="knowledge_base.graph_update_document", bind=True, max_retries=3)
def graph_update_document(self, *, payload: dict) -> dict:
    """Re-extract graph data after a document content change."""
    task = GraphExtractionTask(
        document_id=payload["document_id"],
        user_id=payload["user_id"],
        bucket_id=payload.get("bucket_id", ""),
        title=payload.get("title", ""),
        chunks=payload.get("chunks", []),
        word_count=payload.get("word_count", 0),
        source_url=payload.get("source_url", ""),
    )
    svc = _get_update_service()
    try:
        return _run_async(svc.update_document(task))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="knowledge_base.graph_move_bucket")
def graph_move_bucket(
    *,
    document_id: str,
    new_bucket_id: str,
    new_bucket_name: str,
    new_bucket_path: str,
    user_id: str,
) -> dict:
    """Propagate a bucket move to the graph BELONGS_TO relationship."""
    svc = _get_update_service()
    return svc.move_document_bucket(
        document_id=document_id,
        new_bucket_id=new_bucket_id,
        new_bucket_name=new_bucket_name,
        new_bucket_path=new_bucket_path,
        user_id=user_id,
    )


@celery_app.task(name="knowledge_base.graph_run_pagerank")
def graph_run_pagerank(*, user_id: str = "all") -> dict:
    """Run PageRank computation and write scores back to Kuzu."""
    store = _get_store()
    if user_id == "all":
        # Get all distinct user_ids from Entity table
        rows = store.execute_read(
            "MATCH (e:Entity) RETURN DISTINCT e.user_id", {}
        )
        results = []
        for row in rows:
            uid = str(row[0]) if row else None
            if uid:
                results.append(run_pagerank(config, store, uid))
        return {"status": "ok", "users_processed": len(results)}
    return run_pagerank(config, store, user_id)


@celery_app.task(name="knowledge_base.graph_run_orphan_cleanup")
def graph_run_orphan_cleanup(*, user_id: str = "all") -> dict:
    """Run orphan entity and dangling relationship cleanup."""
    store = _get_store()
    if user_id == "all":
        rows = store.execute_read(
            "MATCH (e:Entity) RETURN DISTINCT e.user_id", {}
        )
        results = []
        for row in rows:
            uid = str(row[0]) if row else None
            if uid:
                results.append(run_orphan_cleanup(config, store, uid))
        return {"status": "ok", "users_processed": len(results)}
    return run_orphan_cleanup(config, store, user_id)


@celery_app.task(name="knowledge_base.graph_run_health_check")
def graph_run_health_check(*, pg_document_count: int = 0) -> dict:
    """Run graph health check against PostgreSQL document count."""
    store = _get_store()
    return run_health_check(config, store, pg_document_count)
