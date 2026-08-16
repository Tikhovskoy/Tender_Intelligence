from types import SimpleNamespace
from typing import Any, cast

import httpx
from openai import BadRequestError

from app.infrastructure.embedding_provider import OpenAICompatibleEmbeddingProvider


class RejectingLargeBatches:
    """Отклоняет пакеты и принимает одиночные фрагменты."""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    async def create(self, *, model: str, input: list[str]) -> Any:
        self.batch_sizes.append(len(input))
        if len(input) > 1:
            request = httpx.Request("POST", "https://provider.test/v1/embeddings")
            response = httpx.Response(400, request=request)
            raise BadRequestError("Пакет слишком велик", response=response, body={})
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[float(len(input[0]))])])


class RecordingEmbeddings:
    """Запоминает режимы построения векторов."""

    def __init__(self) -> None:
        self.input_types: list[str] = []

    async def create(
        self,
        *,
        model: str,
        input: list[str],
        extra_body: dict[str, str],
    ) -> Any:
        self.input_types.append(extra_body["input_type"])
        return SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[1.0])])


async def test_embedding_provider_splits_rejected_batch() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        model="embedding-test",
        base_url="https://provider.test/v1",
        api_key="test-key",
        timeout=10,
        batch_size=8,
    )
    embeddings = RejectingLargeBatches()
    provider.client = cast(Any, SimpleNamespace(embeddings=embeddings))

    vectors = await provider.embed_documents(["первый", "второй", "третий"])

    assert vectors == [[6.0], [6.0], [6.0]]
    assert embeddings.batch_sizes == [3, 1, 2, 1, 1]


async def test_nvidia_embedding_provider_separates_passages_and_queries() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        model="am/nv-embedqa-e5-v5",
        base_url="https://provider.test/v1",
        api_key="test-key",
        timeout=10,
        batch_size=8,
    )
    embeddings = RecordingEmbeddings()
    provider.client = cast(Any, SimpleNamespace(embeddings=embeddings))

    await provider.embed_documents(["условия договора"])
    await provider.embed_query("каковы условия договора?")

    assert embeddings.input_types == ["passage", "query"]
