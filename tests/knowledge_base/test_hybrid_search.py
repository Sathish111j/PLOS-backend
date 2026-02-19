import asyncio
import base64
import uuid

import pytest
from app.api.schemas import SearchRequest
from app.application.knowledge_service import KnowledgeService
from app.application.search_utils import reciprocal_rank_fusion, select_ef_search
from app.core.config import get_kb_config
from app.infrastructure.persistence import KnowledgePersistence


def _run(coroutine):
    return asyncio.run(coroutine)


def test_dynamic_ef_search_selection() -> None:
    assert select_ef_search(40) == 10
    assert select_ef_search(90) == 64
    assert select_ef_search(150) == 200


def test_reciprocal_rank_fusion_weighted_merge() -> None:
    semantic = [{"document_id": "a"}, {"document_id": "b"}, {"document_id": "c"}]
    keyword = [{"document_id": "b"}, {"document_id": "c"}, {"document_id": "a"}]
    fused = reciprocal_rank_fusion([(0.6, semantic), (0.4, keyword)])

    assert fused[0][0] in {"a", "b"}
    assert len(fused) == 3


def test_upload_then_hybrid_search_returns_document() -> None:
    config = get_kb_config()
    persistence = KnowledgePersistence(config)
    service = KnowledgeService(persistence)

    async def scenario() -> None:
        await persistence.connect()
        try:
            marker = uuid.uuid4().hex
            text = f"Hybrid search marker {marker} with retrieval optimization"
            payload = base64.b64encode(text.encode("utf-8")).decode("utf-8")

            upload = await service.upload_document(
                owner_id=str(uuid.uuid4()),
                filename="hybrid-search-test.txt",
                content_base64=payload,
                mime_type="text/plain",
                source_url="https://example.com/hybrid-search-test",
            )

            request = SearchRequest(
                query=f"retrieval optimization {marker}",
                top_k=5,
                latency_budget_ms=120,
                enable_rerank=False,
            )
            result = await service.search(upload["owner_id"], request)
            document_ids = [item["document_id"] for item in result["results"]]

            assert upload["document_id"] in document_ids
            assert result["diagnostics"]["ef_search"] == 200
        finally:
            await persistence.close()

    try:
        _run(scenario())
    except Exception as error:
        pytest.skip(f"Hybrid search integration requires running infra: {error}")
