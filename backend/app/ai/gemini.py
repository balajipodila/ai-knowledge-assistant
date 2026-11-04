from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from google import genai
from google.genai import errors, types
import httpx

from app.ai.errors import (
    EmbeddingProviderError,
    LLMOutputTruncatedError,
    LLMProviderError,
)
from app.ai.interfaces import EmbeddingClient, LLMClient
from app.core.config import Settings


def _retry_after_seconds(error: errors.APIError) -> float | None:
    headers = getattr(error.response, "headers", None)
    if not headers:
        return None

    value = headers.get("Retry-After") or headers.get("retry-after")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


class GeminiEmbeddingClient(EmbeddingClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: genai.Client | None = None

    def embed(self, text: str) -> list[float]:
        vectors = self.embed_many([text])
        return vectors[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        try:
            response = client.models.embed_content(
                model=self.settings.gemini_embedding_model,
                contents=[
                    types.Content(parts=[types.Part(text=text)])
                    for text in texts
                ],
                config=types.EmbedContentConfig(
                    output_dimensionality=self.settings.gemini_embedding_dimension
                ),
            )
        except errors.APIError as error:
            code = error.code
            retryable = code == 429 or code >= 500
            if code == 429:
                message = "Gemini rate limit reached; retry the embedding request."
            elif code >= 500:
                message = "Gemini embedding service is temporarily unavailable."
            else:
                message = "Gemini rejected the embedding request."
            raise EmbeddingProviderError(
                message,
                retryable=retryable,
                status_code=code,
            ) from None
        except (httpx.TransportError, TimeoutError, ConnectionError):
            raise EmbeddingProviderError(
                "Gemini embedding service could not be reached.", retryable=True
            ) from None

        embeddings = response.embeddings
        if embeddings is None or len(embeddings) != len(texts):
            raise EmbeddingProviderError(
                "Gemini returned an incomplete embedding response."
            )

        vectors: list[list[float]] = []
        for embedding in embeddings:
            values = embedding.values
            if values is None or len(values) != self.settings.gemini_embedding_dimension:
                raise EmbeddingProviderError(
                    "Gemini returned an embedding with an unexpected dimension."
                )
            vectors.append([float(value) for value in values])
        return vectors

    def _get_client(self) -> genai.Client:
        if self.settings.gemini_api_key is None:
            raise EmbeddingProviderError(
                "Gemini embeddings are not configured. Set GEMINI_API_KEY."
            )
        if self._client is None:
            self._client = genai.Client(
                api_key=self.settings.gemini_api_key.get_secret_value()
            )
        return self._client


class GeminiLLMClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        client = self._get_client(timeout_seconds)
        try:
            response = client.models.generate_content(
                model=model or self.settings.gemini_chat_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=self.settings.chat_max_output_tokens,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW
                    ),
                ),
            )
        except errors.APIError as error:
            code = error.code
            raise LLMProviderError(
                "Gemini rejected the chat request.",
                retryable=code == 429 or code >= 500,
                status_code=code,
                retry_after_seconds=_retry_after_seconds(error),
            ) from None
        except (httpx.TransportError, TimeoutError, ConnectionError):
            raise LLMProviderError(
                "Gemini chat service could not be reached.", retryable=True
            ) from None
        finally:
            client.close()

        candidates = response.candidates or []
        if candidates and candidates[0].finish_reason == types.FinishReason.MAX_TOKENS:
            raise LLMOutputTruncatedError()
        if not response.text:
            raise LLMProviderError(
                "Gemini returned no chat answer.", status_code=502
            )
        return response.text

    def _get_client(self, timeout_seconds: float | None = None) -> genai.Client:
        if self.settings.gemini_api_key is None:
            raise LLMProviderError(
                "Gemini chat is not configured.", status_code=503
            )
        timeout = (
            self.settings.chat_attempt_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        return genai.Client(
            api_key=self.settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(
                timeout=max(1, round(timeout * 1000)),
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
