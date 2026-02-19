from app.application.ingestion.chunking import ChunkingConfig, SemanticChunkingEngine
from app.application.ingestion.models import (
    ContentClass,
    DocumentFormat,
    ExtractionStrategy,
    StructuredDocument,
)


def _sample_text(paragraphs: int = 60) -> str:
    lines: list[str] = ["# Introduction"]
    for index in range(paragraphs):
        lines.append(
            "\n\n".join(
                [
                    f"Section {index}: This is a semantic paragraph with coherent context and retrieval-friendly structure.",
                    "It keeps sentence boundaries intact and avoids fragmented meaning across chunks.",
                    "The chunking engine should preserve continuity while enforcing token limits for embedding.",
                ]
            )
        )
    return "\n\n".join(lines)


def test_semantic_chunking_generates_metadata_and_overlap() -> None:
    engine = SemanticChunkingEngine(ChunkingConfig())
    structured = StructuredDocument(
        text=_sample_text(),
        metadata={"language": "en"},
        confidence_scores={"text_extraction": 0.99},
        strategy_used=ExtractionStrategy.TEXT_DIRECT,
        format=DocumentFormat.TEXT,
        content_class=ContentClass.TEXT_BASED,
    )

    chunks = engine.chunk_document(
        source_document_id="11111111-1111-1111-1111-111111111111",
        filename="notes.md",
        structured=structured,
    )

    assert len(chunks) >= 2
    assert all(chunk.metadata.get("chunk_index") is not None for chunk in chunks)
    assert all(chunk.metadata.get("total_chunks") == len(chunks) for chunk in chunks)
    assert all(chunk.metadata.get("embedding_model") == "all-MiniLM-L6-v2" for chunk in chunks)

    size_hits = [chunk for chunk in chunks if 256 <= chunk.token_count <= 512]
    assert len(size_hits) / len(chunks) >= 0.6

    first_words = set(chunks[0].text.split()[-40:])
    second_words = set(chunks[1].text.split()[:80])
    assert len(first_words.intersection(second_words)) > 0


def test_table_chunking_keeps_or_splits_with_header() -> None:
    engine = SemanticChunkingEngine(ChunkingConfig())

    rows = [["col1", "col2", "col3"]]
    for idx in range(140):
        rows.append([f"r{idx}", f"value-{idx}", f"description-{idx}"])

    structured = StructuredDocument(
        text="",
        tables=[{"rows": rows}],
        metadata={},
        confidence_scores={"table_extraction": 0.8},
        strategy_used=ExtractionStrategy.PDF_TEXT_FAST,
        format=DocumentFormat.PDF,
        content_class=ContentClass.TEXT_BASED,
    )

    chunks = engine.chunk_document(
        source_document_id="22222222-2222-2222-2222-222222222222",
        filename="table.pdf",
        structured=structured,
    )

    table_chunks = [chunk for chunk in chunks if chunk.metadata.get("content_type") == "table"]
    assert table_chunks
    assert any("(continued)" in chunk.text for chunk in table_chunks)
