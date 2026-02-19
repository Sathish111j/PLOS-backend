import asyncio
import base64
import json
import time
import tracemalloc
from pathlib import Path

import pytest
from app.application.ingestion.format_detector import detect_document_format
from app.application.ingestion.unified_processor import UnifiedDocumentProcessor


FIXTURE_ROOT = Path("tests/fixtures/acceptance")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    previous = list(range(len(b) + 1))
    for index_a, char_a in enumerate(a, start=1):
        current = [index_a]
        for index_b, char_b in enumerate(b, start=1):
            insert_cost = current[index_b - 1] + 1
            delete_cost = previous[index_b] + 1
            replace_cost = previous[index_b - 1] + (0 if char_a == char_b else 1)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def _char_accuracy(predicted: str, expected: str) -> float:
    if not expected:
        return 1.0 if not predicted else 0.0
    distance = _levenshtein(predicted, expected)
    return max(0.0, 1.0 - (distance / max(1, len(expected))))


def _cer(predicted: str, expected: str) -> float:
    if not expected:
        return 0.0
    return _levenshtein(predicted, expected) / max(1, len(expected))


def _wer(predicted: str, expected: str) -> float:
    expected_words = expected.split()
    predicted_words = predicted.split()
    if not expected_words:
        return 0.0
    return _levenshtein("\n".join(predicted_words), "\n".join(expected_words)) / max(
        1, len(expected_words)
    )


def _jaccard(predicted: str, expected: str) -> float:
    a = {token for token in predicted.lower().split() if token}
    b = {token for token in expected.lower().split() if token}
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def _load_cases(file_name: str) -> list[dict]:
    case_file = FIXTURE_ROOT / file_name
    if not case_file.exists():
        pytest.skip(f"Missing benchmark fixture: {case_file}")
    return json.loads(case_file.read_text(encoding="utf-8"))


@pytest.mark.benchmark
def test_pdf_text_extraction_accuracy_threshold() -> None:
    processor = UnifiedDocumentProcessor()
    cases = _load_cases("pdf_text_accuracy.json")

    accuracies: list[float] = []
    for case in cases:
        content_bytes = base64.b64decode(case["content_base64"])
        result = asyncio.run(
            processor.process(
                filename=case.get("filename", "sample.pdf"),
                content_bytes=content_bytes,
                mime_type=case.get("mime_type", "application/pdf"),
                source_url=None,
            )
        )
        accuracies.append(_char_accuracy(result.raw_text, case["expected_text"]))

    assert sum(accuracies) / len(accuracies) > 0.95


@pytest.mark.benchmark
def test_scanned_pdf_cer_threshold() -> None:
    processor = UnifiedDocumentProcessor()
    cases = _load_cases("scanned_pdf_cer.json")

    cer_values: list[float] = []
    for case in cases:
        content_bytes = base64.b64decode(case["content_base64"])
        result = asyncio.run(
            processor.process(
                filename=case.get("filename", "scan.pdf"),
                content_bytes=content_bytes,
                mime_type="application/pdf",
                source_url=None,
            )
        )
        cer_values.append(_cer(result.raw_text, case["expected_text"]))

    assert sum(cer_values) / len(cer_values) < 0.04


@pytest.mark.benchmark
def test_scanned_handwriting_wer_threshold() -> None:
    processor = UnifiedDocumentProcessor()
    cases = _load_cases("scanned_handwriting_wer.json")

    wer_values: list[float] = []
    for case in cases:
        content_bytes = base64.b64decode(case["content_base64"])
        result = asyncio.run(
            processor.process(
                filename=case.get("filename", "handwriting.png"),
                content_bytes=content_bytes,
                mime_type=case.get("mime_type", "image/png"),
                source_url=None,
            )
        )
        wer_values.append(_wer(result.raw_text, case["expected_text"]))

    assert sum(wer_values) / len(wer_values) < 0.30


@pytest.mark.benchmark
def test_web_static_jaccard_threshold() -> None:
    processor = UnifiedDocumentProcessor()
    cases = _load_cases("web_static_similarity.json")

    scores: list[float] = []
    for case in cases:
        result = asyncio.run(
            processor.process(
                filename="from_url",
                content_bytes=None,
                mime_type=None,
                source_url=case["url"],
            )
        )
        scores.append(_jaccard(result.raw_text, case["expected_text"]))

    assert sum(scores) / len(scores) > 0.90


@pytest.mark.benchmark
def test_processing_speed_and_memory_limits() -> None:
    processor = UnifiedDocumentProcessor()
    cases = _load_cases("performance_cases.json")
    case = cases[0]
    content_bytes = base64.b64decode(case["content_base64"])

    tracemalloc.start()
    started = time.perf_counter()
    asyncio.run(
        processor.process(
            filename=case.get("filename", "benchmark.pdf"),
            content_bytes=content_bytes,
            mime_type=case.get("mime_type", "application/pdf"),
            source_url=None,
        )
    )
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert elapsed < 10.0
    assert peak < 2 * 1024 * 1024 * 1024


@pytest.mark.benchmark
def test_concurrent_upload_resilience() -> None:
    processor = UnifiedDocumentProcessor()
    payload = base64.b64encode(b"concurrency benchmark text").decode("utf-8")

    async def task(index: int):
        result = await processor.process(
            filename=f"batch-{index}.txt",
            content_bytes=base64.b64decode(payload),
            mime_type="text/plain",
            source_url=None,
        )
        return bool(result.raw_text)

    async def run_batch() -> list[bool]:
        return await asyncio.gather(*[task(i) for i in range(10)])

    outcomes = asyncio.run(run_batch())
    assert all(outcomes)


@pytest.mark.benchmark
def test_format_detection_accuracy_threshold() -> None:
    cases = _load_cases("format_detection_cases.json")

    correct = 0
    for case in cases:
        detected = detect_document_format(
            filename=case["filename"],
            content_bytes=base64.b64decode(case.get("content_base64", ""))
            if case.get("content_base64")
            else None,
            mime_type=case.get("mime_type"),
            source_url=case.get("source_url"),
        )
        if detected.format.value == case["expected_format"]:
            correct += 1

    accuracy = correct / len(cases)
    assert accuracy > 0.995
