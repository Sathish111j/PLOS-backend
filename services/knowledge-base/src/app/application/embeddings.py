import math

from app.application.search_utils import deterministic_embedding
from app.core.config import KnowledgeBaseConfig

from shared.gemini.client import ResilientGeminiClient
from shared.gemini.config import get_gemini_config
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class GeminiEmbeddingProvider:
    def __init__(self, config: KnowledgeBaseConfig):
        self._config = config
        self._gemini_client: ResilientGeminiClient | None = None
        gemini_config = get_gemini_config()
        self._embedding_model = gemini_config.embedding_model
        self._dimensions = int(getattr(config, "embedding_dimensions", 384))

    def _candidate_models(self) -> list[str]:
        candidates = [
            self._embedding_model,
            "gemini-embedding-001",
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for model in candidates:
            if model and model not in seen:
                ordered.append(model)
                seen.add(model)
        return ordered

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _resize_vector(source: list[float], target_dim: int) -> list[float]:
        if not source:
            return [0.0] * target_dim
        if len(source) == target_dim:
            return source

        if len(source) > target_dim:
            bucket_size = len(source) / target_dim
            resized: list[float] = []
            for index in range(target_dim):
                start = int(index * bucket_size)
                end = int((index + 1) * bucket_size)
                if end <= start:
                    end = start + 1
                segment = source[start:end]
                resized.append(sum(segment) / len(segment))
            return resized

        resized = [0.0] * target_dim
        for index in range(target_dim):
            resized[index] = source[index % len(source)]
        return resized

    async def _gemini_embedding(
        self,
        text: str,
        *,
        task_type: str,
    ) -> list[float] | None:
        if self._gemini_client is None:
            try:
                self._gemini_client = ResilientGeminiClient()
            except Exception as error:
                logger.warning(
                    "Gemini client unavailable; using deterministic fallback",
                    extra={"error": str(error)},
                )
                return None

        last_error: Exception | None = None
        for model_name in self._candidate_models():
            try:
                vector = await self._gemini_client.embed_content(
                    text,
                    model=model_name,
                    task_type=task_type,
                    output_dimensionality=self._dimensions,
                )
                resized = self._resize_vector(
                    [float(value) for value in vector],
                    self._dimensions,
                )
                return self._normalize(resized)
            except Exception as error:
                last_error = error
                logger.warning(
                    "Gemini embedding model attempt failed",
                    extra={"error": str(error), "model": model_name},
                )

        logger.warning(
            "Gemini embedding failed for all candidate models; using deterministic fallback",
            extra={"error": str(last_error) if last_error else None},
        )
        return None

    async def _embed_with_fallback(self, text: str, *, task_type: str) -> list[float]:
        vector = await self._gemini_embedding(text, task_type=task_type)
        if vector:
            return vector
        return deterministic_embedding(text, dimension=self._dimensions)

    async def embed_document(self, text: str) -> list[float]:
        return await self._embed_with_fallback(
            text,
            task_type="RETRIEVAL_DOCUMENT",
        )

    async def embed_query(self, text: str) -> list[float]:
        return await self._embed_with_fallback(
            text,
            task_type="RETRIEVAL_QUERY",
        )

    async def embed_text(self, text: str) -> list[float]:
        return await self.embed_document(text)
