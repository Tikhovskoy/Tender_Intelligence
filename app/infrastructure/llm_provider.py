"""OpenAI-совместимый провайдер структурированного анализа."""

from collections.abc import Sequence

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.domain.documents import VectorSearchResult
from app.domain.exceptions import InvalidProviderResponseError, ProviderUnavailableError
from app.domain.rag import ANSWER_NOT_FOUND, GroundedAnswerDraft
from app.domain.tender import NOT_FOUND, AnalysisChunk, TenderCard


class OpenAICompatibleTenderProvider:
    """Вызов облачного или локального OpenAI-совместимого API."""

    def __init__(
        self,
        *,
        name: str,
        model: str,
        base_url: str,
        api_key: str,
        timeout: float,
    ) -> None:
        self.name = name
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=1,
        )

    async def analyze(self, chunks: Sequence[AnalysisChunk]) -> TenderCard:
        context = "\n\n".join(
            f"[ФРАГМЕНТ {chunk.chunk_index}; СТРАНИЦА {chunk.page_number}]\n{chunk.text}"
            for chunk in chunks
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Извлеки карточку тендера только из переданных фрагментов. "
                            f"Если значение отсутствует, используй строку «{NOT_FOUND}». "
                            "Для найденных значений приводи короткие точные цитаты. "
                            "Не добавляй сведения, которых нет в контексте."
                        ),
                    },
                    {"role": "user", "content": context},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "tender_card",
                        "strict": True,
                        "schema": TenderCard.model_json_schema(),
                    },
                },
            )
        except OpenAIError as error:
            raise ProviderUnavailableError(
                "Провайдер анализа временно недоступен",
                code="analysis_provider_unavailable",
            ) from error

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise InvalidProviderResponseError(
                "Провайдер вернул пустой ответ",
                code="analysis_response_empty",
            )
        try:
            return TenderCard.model_validate_json(content)
        except ValidationError as error:
            raise InvalidProviderResponseError(
                "Провайдер вернул ответ неверного формата",
                code="analysis_response_invalid",
            ) from error

    async def answer_question(
        self,
        question: str,
        chunks: Sequence[VectorSearchResult],
    ) -> GroundedAnswerDraft:
        """Ответить только по контексту семантического поиска."""
        context = "\n\n".join(
            (
                f"[ИСТОЧНИК {position}; СТРАНИЦА {chunk.page_number}; "
                f"РЕЛЕВАНТНОСТЬ {chunk.relevance:.4f}]\n{chunk.text}"
            )
            for position, chunk in enumerate(chunks, start=1)
        )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ответь на вопрос только по переданным источникам. "
                            "Не используй внешние знания и не придумывай факты. "
                            "Если контекста недостаточно, установи context_sufficient=false "
                            f"и верни точную строку «{ANSWER_NOT_FOUND}»."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"ВОПРОС:\n{question}\n\nИСТОЧНИКИ:\n{context}",
                    },
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "grounded_answer",
                        "strict": True,
                        "schema": GroundedAnswerDraft.model_json_schema(),
                    },
                },
            )
        except OpenAIError as error:
            raise ProviderUnavailableError(
                "Провайдер ответов временно недоступен",
                code="answer_provider_unavailable",
            ) from error

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise InvalidProviderResponseError(
                "Провайдер вернул пустой ответ",
                code="answer_response_empty",
            )
        try:
            return GroundedAnswerDraft.model_validate_json(content)
        except ValidationError as error:
            raise InvalidProviderResponseError(
                "Провайдер вернул ответ неверного формата",
                code="answer_response_invalid",
            ) from error
