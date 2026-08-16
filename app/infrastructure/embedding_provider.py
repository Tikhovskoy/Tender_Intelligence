"""OpenAI-совместимое построение векторных представлений."""

from collections.abc import Sequence

from openai import AsyncOpenAI, BadRequestError, OpenAIError

from app.domain.exceptions import InvalidProviderResponseError, ProviderUnavailableError


class OpenAICompatibleEmbeddingProvider:
    """Пакетные embeddings для облачного API или Ollama."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float,
        batch_size: int,
    ) -> None:
        self.model = model
        self.batch_size = batch_size
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=3,
        )

    async def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(await self._embed(texts[start : start + self.batch_size]))
        return vectors

    async def embed_query(self, text: str) -> Sequence[float]:
        vectors = await self._embed([text])
        return vectors[0]

    async def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=list(texts),
            )
        except BadRequestError as error:
            if len(texts) > 1:
                middle = len(texts) // 2
                left = await self._embed(texts[:middle])
                right = await self._embed(texts[middle:])
                return [*left, *right]
            raise InvalidProviderResponseError(
                "Embedding-модель отклонила фрагмент документа",
                code="embedding_request_rejected",
            ) from error
        except OpenAIError as error:
            raise ProviderUnavailableError(
                "Провайдер embeddings временно недоступен",
                code="embedding_provider_unavailable",
            ) from error
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors = [item.embedding for item in ordered]
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise InvalidProviderResponseError(
                "Провайдер embeddings вернул неверный ответ",
                code="embedding_response_invalid",
            )
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1:
            raise InvalidProviderResponseError(
                "Провайдер embeddings вернул векторы разной размерности",
                code="embedding_dimensions_invalid",
            )
        return vectors
