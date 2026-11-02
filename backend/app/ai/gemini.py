from google import genai
from google.genai import errors, types
import httpx

from app.ai.errors import EmbeddingProviderError
from app.ai.interfaces import EmbeddingClient
from app.core.config import Settings


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
