from types import SimpleNamespace
from typing import Any

from google.genai import types

from app.ai.gemini import GeminiEmbeddingClient
from app.core.config import Settings


def test_gemini_client_uses_configured_model_dimension_and_secret(
    monkeypatch: Any,
) -> None:
    class FakeModels:
        def __init__(self) -> None:
            self.arguments: dict[str, object] | None = None

        def embed_content(self, **arguments: object) -> SimpleNamespace:
            self.arguments = arguments
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.25] * 768) for _ in range(2)]
            )

    class FakeSDKClient:
        def __init__(self) -> None:
            self.models = FakeModels()

    sdk_client = FakeSDKClient()

    def build_client(**arguments: object) -> FakeSDKClient:
        assert arguments == {"api_key": "unit-test-api-key"}
        return sdk_client

    monkeypatch.setattr("app.ai.gemini.genai.Client", build_client)
    settings = Settings.model_validate(
        {
            "gemini_api_key": "unit-test-api-key",
            "gemini_embedding_model": "gemini-embedding-2",
            "gemini_embedding_dimension": 768,
        }
    )
    client = GeminiEmbeddingClient(settings)

    vectors = client.embed_many(["prepared document", "prepared query"])

    assert len(vectors) == 2
    assert all(len(vector) == 768 for vector in vectors)
    arguments = sdk_client.models.arguments
    assert arguments is not None
    assert arguments["model"] == "gemini-embedding-2"
    assert arguments["contents"] == [
        types.Content(parts=[types.Part(text="prepared document")]),
        types.Content(parts=[types.Part(text="prepared query")]),
    ]
    config = arguments["config"]
    assert isinstance(config, types.EmbedContentConfig)
    assert config.output_dimensionality == 768
