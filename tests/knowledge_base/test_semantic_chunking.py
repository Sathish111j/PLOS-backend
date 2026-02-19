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
    assert all(chunk.metadata.get("embedding_model") == "gemini-embedding-001" for chunk in chunks)
    assert all(chunk.metadata.get("document_id") == "11111111-1111-1111-1111-111111111111" for chunk in chunks)
    assert all("split_boundary" in chunk.metadata for chunk in chunks)
    assert all("bucket_id" in chunk.metadata for chunk in chunks)
    assert all("parent_chunk_id" in chunk.metadata for chunk in chunks)

    size_hits = [chunk for chunk in chunks if 256 <= chunk.token_count <= 768]
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


def test_chunking_default_parameters_match_spec() -> None:
    config = ChunkingConfig()
    assert config.target_tokens == 512
    assert config.max_tokens == 768
    assert config.min_tokens == 100
    assert config.overlap_tokens == 100
    assert config.table_single_chunk_limit == 400


def test_image_pair_chunk_generation() -> None:
    engine = SemanticChunkingEngine(ChunkingConfig())
    structured = StructuredDocument(
        text="Before image paragraph.\n\nAfter image paragraph.",
        images=[{"id": "img-1", "description": "A sample chart", "page": 2}],
        metadata={},
        confidence_scores={"text_extraction": 0.9},
        strategy_used=ExtractionStrategy.PDF_MIXED_HYBRID,
        format=DocumentFormat.PDF,
        content_class=ContentClass.MIXED,
    )

    chunks = engine.chunk_document(
        source_document_id="33333333-3333-3333-3333-333333333333",
        filename="image-pair.pdf",
        structured=structured,
    )

    image_pair_chunks = [
        chunk for chunk in chunks if chunk.metadata.get("content_type") == "image_pair"
    ]
    assert image_pair_chunks
    assert any(chunk.metadata.get("has_image") is True for chunk in image_pair_chunks)
    assert any("img-1" in (chunk.metadata.get("image_ids") or []) for chunk in image_pair_chunks)


def test_code_chunk_metadata_contains_path_language_and_lines() -> None:
    engine = SemanticChunkingEngine(ChunkingConfig())
    code_text = """
def alpha():
    return 1

class Beta:
    def gamma(self):
        return 2
""".strip()

    structured = StructuredDocument(
        text=code_text,
        metadata={},
        confidence_scores={"text_extraction": 0.95},
        strategy_used=ExtractionStrategy.TEXT_DIRECT,
        format=DocumentFormat.TEXT,
        content_class=ContentClass.TEXT_BASED,
    )

    chunks = engine.chunk_document(
        source_document_id="44444444-4444-4444-4444-444444444444",
        filename="sample.py",
        structured=structured,
    )

    code_chunks = [chunk for chunk in chunks if chunk.metadata.get("content_type") == "code"]
    assert code_chunks
    assert all(chunk.metadata.get("language") == "python" for chunk in code_chunks)
    assert all(chunk.metadata.get("file_path") == "sample.py" for chunk in code_chunks)
    assert all(chunk.metadata.get("start_line") is not None for chunk in code_chunks)
    assert all(chunk.metadata.get("end_line") is not None for chunk in code_chunks)
