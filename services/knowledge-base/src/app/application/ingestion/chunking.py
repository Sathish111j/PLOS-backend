from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterator
from uuid import uuid4

from app.application.ingestion.models import DocumentChunk, StructuredDocument


@dataclass(frozen=True)
class ChunkingConfig:
    target_tokens: int = 512
    max_tokens: int = 768
    min_tokens: int = 100
    overlap_tokens: int = 100
    table_single_chunk_limit: int = 400
    token_spot_check_interval_chars: int = 1000


@dataclass(frozen=True)
class _ChunkUnit:
    text: str
    section_heading: str | None = None
    content_type: str = "text"
    page_range: tuple[int, int] | None = None
    line_range: tuple[int, int] | None = None
    language: str | None = None
    file_path: str | None = None
    split_boundary: str = "section"
    parent_chunk_id: str | None = None
    image_ids: list[str] | None = None


class FastTokenEstimator:
    def __init__(self, spot_check_interval_chars: int = 1000):
        self._spot_check_interval_chars = spot_check_interval_chars
        self._correction_factor = 1.0

    def estimate(self, text: str) -> int:
        if not text:
            return 0
        ratio = self._ratio_for_text(text)
        estimate = max(1, int((len(text) / ratio) * self._correction_factor))
        if len(text) >= self._spot_check_interval_chars:
            actual = self._spot_check_token_count(text)
            if actual > 0:
                self._correction_factor = actual / max(1, int(len(text) / ratio))
                estimate = max(1, int((len(text) / ratio) * self._correction_factor))
        return estimate

    def _ratio_for_text(self, text: str) -> float:
        cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        if cjk_chars / max(1, len(text)) > 0.2:
            return 1.0

        code_markers = re.findall(
            r"\b(def|class|function|return|import|from|if|else|for|while|const|let|var)\b|[{};<>]=?",
            text,
        )
        if len(code_markers) >= 8:
            return 3.5
        return 4.0

    def _spot_check_token_count(self, text: str) -> int:
        return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


class SemanticChunkingEngine:
    def __init__(self, config: ChunkingConfig | None = None):
        self._config = config or ChunkingConfig()
        self._estimator = FastTokenEstimator(
            self._config.token_spot_check_interval_chars
        )

    def chunk_document(
        self,
        *,
        source_document_id: str,
        filename: str,
        structured: StructuredDocument,
        embedding_model: str = "gemini-embedding-001",
        queue_is_full: Callable[[], bool] | None = None,
    ) -> list[DocumentChunk]:
        chunks = list(
            self.iter_chunks(
                source_document_id=source_document_id,
                filename=filename,
                structured=structured,
                embedding_model=embedding_model,
                queue_is_full=queue_is_full,
            )
        )

        total_chunks = len(chunks)
        for index, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = index
            chunk.metadata["total_chunks"] = total_chunks
        return chunks

    def iter_chunks(
        self,
        *,
        source_document_id: str,
        filename: str,
        structured: StructuredDocument,
        embedding_model: str = "gemini-embedding-001",
        queue_is_full: Callable[[], bool] | None = None,
    ) -> Iterator[DocumentChunk]:
        units = self._build_units(filename, structured)
        if self._use_fixed_size_strategy(
            filename, structured.text, structured.metadata
        ):
            candidate_chunks = self._chunk_fixed_size(units)
            strategy = "fixed_overlap"
        else:
            candidate_chunks = self._chunk_semantic(units)
            strategy = "recursive_semantic"

        for chunk in candidate_chunks:
            if queue_is_full:
                while queue_is_full():
                    time.sleep(0.05)

            chunk_id = str(uuid4())
            token_count = self._estimator.estimate(chunk.text)
            image_ids = list(chunk.image_ids or [])
            metadata = {
                "chunk_id": chunk_id,
                "document_id": source_document_id,
                "section_heading": chunk.section_heading,
                "page_range": list(chunk.page_range) if chunk.page_range else None,
                "parent_chunk_id": chunk.parent_chunk_id,
                "token_count": token_count,
                "char_count": len(chunk.text),
                "embedding_model": embedding_model,
                "content_type": chunk.content_type,
                "split_boundary": chunk.split_boundary,
                "line_range": list(chunk.line_range) if chunk.line_range else None,
                "has_image": bool(image_ids),
                "image_ids": image_ids,
                "bucket_id": None,
                "chunking_strategy": strategy,
            }
            if chunk.language:
                metadata["language"] = chunk.language
            if chunk.file_path:
                metadata["file_path"] = chunk.file_path
            if chunk.line_range:
                metadata["start_line"] = chunk.line_range[0]
                metadata["end_line"] = chunk.line_range[1]

            yield DocumentChunk(
                chunk_id=chunk_id,
                text=chunk.text,
                metadata=metadata,
                token_count=token_count,
                char_count=len(chunk.text),
            )

    def _build_units(
        self, filename: str, structured: StructuredDocument
    ) -> list[_ChunkUnit]:
        units: list[_ChunkUnit] = []

        table_units = self._table_units(structured.tables)
        units.extend(table_units)

        code_units = self._code_units(filename, structured.text)
        if code_units:
            units.extend(code_units)
        else:
            units.extend(self._text_units(structured.text))

        image_pair_units = self._image_pair_units(structured.text, structured.images)
        units.extend(image_pair_units)

        if not units and structured.text.strip():
            units.append(_ChunkUnit(text=structured.text.strip(), split_boundary="section"))
        return units

    def _image_pair_units(self, text: str, images: list[dict[str, Any]]) -> list[_ChunkUnit]:
        if not images:
            return []

        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            paragraphs = [text.strip()] if text.strip() else []

        units: list[_ChunkUnit] = []
        for index, image in enumerate(images):
            image_id = str(image.get("id") or uuid4())
            page = image.get("page")
            ocr_text = str(image.get("ocr_text") or image.get("description") or "").strip()

            before = paragraphs[max(0, index - 1)] if paragraphs else ""
            after = paragraphs[min(len(paragraphs) - 1, index)] if paragraphs else ""
            combined = "\n\n".join(part for part in [before, ocr_text, after] if part).strip()
            if not combined:
                continue

            page_range = None
            if isinstance(page, int):
                page_range = (page, page)

            units.append(
                _ChunkUnit(
                    text=combined,
                    content_type="image_pair",
                    page_range=page_range,
                    split_boundary="section",
                    image_ids=[image_id],
                    section_heading=f"Image {index + 1}",
                )
            )

        return units

    def _table_units(self, tables: list[dict[str, Any]]) -> list[_ChunkUnit]:
        table_units: list[_ChunkUnit] = []
        for table_index, table in enumerate(tables):
            rows = table.get("rows") or []
            if not rows:
                continue
            header = rows[0] if rows else []
            header_line = " | ".join("" if col is None else str(col) for col in header)

            all_lines = [
                " | ".join("" if cell is None else str(cell) for cell in row)
                for row in rows
            ]
            rendered = "\n".join(all_lines)
            token_count = self._estimator.estimate(rendered)

            if token_count <= self._config.table_single_chunk_limit:
                table_units.append(
                    _ChunkUnit(
                        text=rendered,
                        content_type="table",
                        section_heading=f"Table {table_index + 1}",
                        split_boundary="section",
                    )
                )
                continue

            data_rows = rows[1:] if len(rows) > 1 else rows
            row_bucket: list[str] = []
            for row in data_rows:
                row_bucket.append(
                    " | ".join("" if cell is None else str(cell) for cell in row)
                )
                candidate = "\n".join([header_line + " (continued)", *row_bucket])
                if (
                    self._estimator.estimate(candidate) > self._config.target_tokens
                    and len(row_bucket) > 1
                ):
                    carry = row_bucket.pop()
                    split_text = "\n".join([header_line + " (continued)", *row_bucket])
                    table_units.append(
                        _ChunkUnit(
                            text=split_text,
                            content_type="table",
                            section_heading=f"Table {table_index + 1}",
                            split_boundary="clause",
                        )
                    )
                    row_bucket = [carry]

            if row_bucket:
                split_text = "\n".join([header_line + " (continued)", *row_bucket])
                table_units.append(
                    _ChunkUnit(
                        text=split_text,
                        content_type="table",
                        section_heading=f"Table {table_index + 1}",
                        split_boundary="clause",
                    )
                )

        return table_units

    def _code_units(self, filename: str, text: str) -> list[_ChunkUnit]:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix == "py":
            return self._python_code_units(filename, text)
        if suffix in {"js", "mjs", "cjs", "ts", "tsx", "jsx"}:
            return self._javascript_code_units(filename, text)
        return []

    def _python_code_units(self, filename: str, text: str) -> list[_ChunkUnit]:
        if not text.strip():
            return []

        lines = text.splitlines()
        try:
            parsed = ast.parse(text)
        except Exception:
            return self._generic_code_blocks(text)

        code_units: list[_ChunkUnit] = []
        for node in parsed.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                snippet = "\n".join(lines[start - 1 : end]).strip()
                if snippet:
                    code_units.append(
                        _ChunkUnit(
                            text=snippet,
                            content_type="code",
                            language="python",
                            line_range=(start, end),
                            section_heading=getattr(node, "name", None),
                            file_path=filename,
                            split_boundary="section",
                        )
                    )

        if code_units:
            return code_units
        return self._generic_code_blocks(text)

    def _javascript_code_units(self, filename: str, text: str) -> list[_ChunkUnit]:
        if not text.strip():
            return []

        pattern = re.compile(
            r"(^\s*(?:export\s+)?(?:async\s+)?function\s+[A-Za-z0-9_]+\s*\(|^\s*(?:const|let|var)\s+[A-Za-z0-9_]+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
            re.MULTILINE,
        )
        matches = list(pattern.finditer(text))
        if not matches:
            return self._generic_code_blocks(text)

        units: list[_ChunkUnit] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            snippet = text[start:end].strip()
            if snippet:
                line_start = text[:start].count("\n") + 1
                line_end = text[:end].count("\n") + 1
                units.append(
                    _ChunkUnit(
                        text=snippet,
                        content_type="code",
                        language="javascript",
                        line_range=(line_start, line_end),
                        file_path=filename,
                        split_boundary="section",
                    )
                )
        return units

    def _generic_code_blocks(self, text: str) -> list[_ChunkUnit]:
        blocks = [
            block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()
        ]
        return [
            _ChunkUnit(text=block, content_type="code", split_boundary="paragraph")
            for block in blocks
        ]

    def _text_units(self, text: str) -> list[_ChunkUnit]:
        if not text.strip():
            return []

        section_pattern = re.compile(r"(?m)^(#{1,6}\s+.+)$")
        sections = section_pattern.split(text)

        if len(sections) <= 1:
            return [_ChunkUnit(text=text.strip(), split_boundary="section")]

        units: list[_ChunkUnit] = []
        current_heading: str | None = None
        for part in sections:
            normalized = part.strip()
            if not normalized:
                continue
            if section_pattern.match(normalized):
                current_heading = normalized.lstrip("#").strip()
                continue
            units.append(
                _ChunkUnit(
                    text=normalized,
                    section_heading=current_heading,
                    split_boundary="section",
                )
            )
        return units

    def _chunk_semantic(self, units: list[_ChunkUnit]) -> list[_ChunkUnit]:
        expanded: list[_ChunkUnit] = []
        for unit in units:
            expanded.extend(self._recursive_split_unit(unit, 0))

        combined = self._combine_units_with_overlap(expanded)
        return self._enforce_minimum_size(combined)

    def _recursive_split_unit(self, unit: _ChunkUnit, level: int) -> list[_ChunkUnit]:
        if self._estimator.estimate(unit.text) <= self._config.max_tokens:
            return [unit]

        splitters: list[tuple[str, Callable[[str], list[str]]]] = [
            ("section", self._split_by_sections),
            ("paragraph", self._split_by_paragraphs),
            ("sentence", self._split_by_sentences),
            ("clause", self._split_by_clauses),
            ("word", self._split_by_words),
        ]

        if level >= len(splitters):
            return [unit]

        split_boundary, splitter = splitters[level]
        parts = splitter(unit.text)
        if len(parts) <= 1:
            return self._recursive_split_unit(unit, level + 1)

        output: list[_ChunkUnit] = []
        for part in parts:
            part_text = part.strip()
            if not part_text:
                continue
            output.extend(
                self._recursive_split_unit(
                    _ChunkUnit(
                        text=part_text,
                        section_heading=unit.section_heading,
                        content_type=unit.content_type,
                        page_range=unit.page_range,
                        line_range=unit.line_range,
                        language=unit.language,
                        file_path=unit.file_path,
                        split_boundary=split_boundary,
                        image_ids=unit.image_ids,
                    ),
                    level + 1,
                )
            )
        return output

    def _split_by_sections(self, text: str) -> list[str]:
        chunks = [
            part.strip()
            for part in re.split(r"(?m)(?=^#{1,6}\s+)|(?=^\[Page\s+\d+\])", text)
            if part.strip()
        ]
        return chunks if chunks else [text]

    def _split_by_paragraphs(self, text: str) -> list[str]:
        chunks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        return chunks if chunks else [text]

    def _split_by_sentences(self, text: str) -> list[str]:
        chunks = [
            part.strip()
            for part in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
            if part.strip()
        ]
        return chunks if chunks else [text]

    def _split_by_clauses(self, text: str) -> list[str]:
        chunks = [
            part.strip() for part in re.split(r"(?<=[,;:])\s+", text) if part.strip()
        ]
        return chunks if chunks else [text]

    def _split_by_words(self, text: str) -> list[str]:
        words = text.split()
        if not words:
            return [text]

        pieces: list[str] = []
        cursor = 0
        approx_words = max(50, self._config.target_tokens)
        while cursor < len(words):
            segment = " ".join(words[cursor : cursor + approx_words]).strip()
            if segment:
                pieces.append(segment)
            cursor += approx_words
        return pieces if pieces else [text]

    def _chunk_fixed_size(self, units: list[_ChunkUnit]) -> list[_ChunkUnit]:
        text = "\n\n".join(unit.text for unit in units if unit.text.strip())
        words = text.split()
        if not words:
            return []

        step = max(1, self._config.target_tokens - self._config.overlap_tokens)
        output: list[_ChunkUnit] = []
        cursor = 0
        while cursor < len(words):
            block = " ".join(
                words[cursor : cursor + self._config.target_tokens]
            ).strip()
            if block:
                output.append(_ChunkUnit(text=block, split_boundary="word"))
            cursor += step
        return output

    def _combine_units_with_overlap(self, units: list[_ChunkUnit]) -> list[_ChunkUnit]:
        output: list[_ChunkUnit] = []
        current = ""
        current_heading: str | None = None
        current_content_type: str | None = None
        current_split_boundary: str = "section"
        current_language: str | None = None
        current_line_range: tuple[int, int] | None = None
        current_file_path: str | None = None
        current_image_ids: list[str] = []

        for unit in units:
            unit_text = unit.text.strip()
            if not unit_text:
                continue

            if unit.content_type in {"table", "code", "image_pair"}:
                if current:
                    output.append(
                        _ChunkUnit(
                            text=current,
                            section_heading=current_heading,
                            content_type=current_content_type or "text",
                            split_boundary=current_split_boundary,
                            language=current_language,
                            line_range=current_line_range,
                            file_path=current_file_path,
                            image_ids=list(current_image_ids),
                        )
                    )
                    current = ""
                    current_heading = None
                    current_content_type = None
                    current_split_boundary = "section"
                    current_language = None
                    current_line_range = None
                    current_file_path = None
                    current_image_ids = []

                output.append(unit)
                continue

            candidate = f"{current}\n\n{unit_text}".strip() if current else unit_text
            if (
                current
                and self._estimator.estimate(candidate) > self._config.target_tokens
            ):
                output.append(
                    _ChunkUnit(
                        text=current,
                        section_heading=current_heading,
                        content_type=current_content_type or unit.content_type,
                        split_boundary=current_split_boundary,
                        language=current_language,
                        line_range=current_line_range,
                        file_path=current_file_path,
                        image_ids=list(current_image_ids),
                    )
                )
                overlap = self._tail_overlap(current)
                current = f"{overlap}\n\n{unit_text}".strip() if overlap else unit_text
                current_heading = unit.section_heading or current_heading
                current_content_type = unit.content_type
                current_split_boundary = unit.split_boundary
                current_language = unit.language
                current_line_range = unit.line_range
                current_file_path = unit.file_path
                current_image_ids = list(unit.image_ids or [])
            else:
                current = candidate
                current_heading = unit.section_heading or current_heading
                if current_content_type and current_content_type != unit.content_type:
                    current_content_type = "mixed"
                else:
                    current_content_type = unit.content_type
                current_split_boundary = unit.split_boundary
                current_language = unit.language or current_language
                current_line_range = unit.line_range or current_line_range
                current_file_path = unit.file_path or current_file_path
                current_image_ids = list({*current_image_ids, *(unit.image_ids or [])})

        if current:
            output.append(
                _ChunkUnit(
                    text=current,
                    section_heading=current_heading,
                    content_type=current_content_type or "text",
                    split_boundary=current_split_boundary,
                    language=current_language,
                    line_range=current_line_range,
                    file_path=current_file_path,
                    image_ids=list(current_image_ids),
                )
            )

        return output

    def _tail_overlap(self, text: str) -> str:
        words = text.split()
        if not words:
            return ""
        return " ".join(words[-self._config.overlap_tokens :])

    def _enforce_minimum_size(self, chunks: list[_ChunkUnit]) -> list[_ChunkUnit]:
        if not chunks:
            return chunks

        merged: list[_ChunkUnit] = []
        for chunk in chunks:
            token_count = self._estimator.estimate(chunk.text)
            if (
                merged
                and token_count < self._config.min_tokens
                and chunk.content_type not in {"table", "code", "image_pair"}
                and merged[-1].content_type not in {"table", "code", "image_pair"}
            ):
                previous = merged.pop()
                merged_text = f"{previous.text}\n\n{chunk.text}".strip()
                if self._estimator.estimate(merged_text) > self._config.max_tokens:
                    merged.append(previous)
                    merged.append(chunk)
                    continue
                merged.append(
                    _ChunkUnit(
                        text=merged_text,
                        section_heading=previous.section_heading
                        or chunk.section_heading,
                        content_type=(
                            previous.content_type
                            if previous.content_type == chunk.content_type
                            else "mixed"
                        ),
                        split_boundary=chunk.split_boundary,
                        language=previous.language or chunk.language,
                        line_range=previous.line_range or chunk.line_range,
                        file_path=previous.file_path or chunk.file_path,
                        image_ids=list({*(previous.image_ids or []), *(chunk.image_ids or [])}),
                    )
                )
            else:
                merged.append(chunk)

        return merged

    def _use_fixed_size_strategy(
        self, filename: str, text: str, metadata: dict[str, Any]
    ) -> bool:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in {"json", "log", "yaml", "yml", "xml"}:
            return True

        if metadata.get("text_subtype") in {"json", "xml", "csv", "log"}:
            return True

        lines = [line for line in text.splitlines() if line.strip()]
        if len(lines) < 20:
            return False

        unique_ratio = len(set(lines)) / len(lines)
        return unique_ratio < 0.45
