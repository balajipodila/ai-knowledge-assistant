from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors, types

from app.ai.errors import LLMOutputTruncatedError, LLMProviderError
from app.ai.gemini import GeminiLLMClient
from app.core.config import Settings


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        GEMINI_API_KEY="test-only-api-key",
        GEMINI_CHAT_MODEL="gemini-test-model",
        CHAT_MAX_OUTPUT_TOKENS=2048,
        CHAT_TIMEOUT_SECONDS=11,
    )


def test_gemini_client_uses_model_timeout_output_cap_and_low_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Models:
        def generate_content(self, **kwargs: object) -> SimpleNamespace:
            captured["request"] = kwargs
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(finish_reason=types.FinishReason.STOP)
                ],
                text="Grounded answer [1].",
            )

    class ClientStub:
        def __init__(self, **kwargs: object) -> None:
            captured["client"] = kwargs
            self.models = Models()

    monkeypatch.setattr("app.ai.gemini.genai.Client", ClientStub)
    client = GeminiLLMClient(_settings())

    result = client.generate(
        "context",
        system_instruction="Answer only from context.",
    )

    client_options = captured["client"]
    assert isinstance(client_options, dict)
    http_options = client_options["http_options"]
    assert isinstance(http_options, types.HttpOptions)
    assert http_options.timeout == 11000
    assert http_options.retry_options is not None
    assert http_options.retry_options.attempts == 1
    request = captured["request"]
    assert isinstance(request, dict)
    assert request["model"] == "gemini-test-model"
    generation_config = request["config"]
    assert isinstance(generation_config, types.GenerateContentConfig)
    assert generation_config.max_output_tokens == 2048
    assert generation_config.system_instruction == "Answer only from context."
    assert generation_config.thinking_config is not None
    assert generation_config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert result == "Grounded answer [1]."


def test_gemini_client_rejects_max_token_finish_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Models:
        def generate_content(self, **_kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                candidates=[
                    SimpleNamespace(finish_reason=types.FinishReason.MAX_TOKENS)
                ],
                text="Partial answer [1]",
            )

    class ClientStub:
        def __init__(self, **_kwargs: object) -> None:
            self.models = Models()

    monkeypatch.setattr("app.ai.gemini.genai.Client", ClientStub)

    with pytest.raises(LLMOutputTruncatedError):
        GeminiLLMClient(_settings()).generate("context")


def test_gemini_client_preserves_retry_after_without_exposing_provider_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Models:
        def generate_content(self, **_kwargs: object) -> None:
            response = httpx.Response(
                429,
                headers={"Retry-After": "17"},
                request=httpx.Request("POST", "https://example.test"),
            )
            raise errors.APIError(
                429,
                {"error": {"message": "private provider detail"}},
                response=response,
            )

    class ClientStub:
        def __init__(self, **_kwargs: object) -> None:
            self.models = Models()

    monkeypatch.setattr("app.ai.gemini.genai.Client", ClientStub)

    with pytest.raises(LLMProviderError) as raised:
        GeminiLLMClient(_settings()).generate("context")

    assert raised.value.status_code == 429
    assert raised.value.retry_after_seconds == 17
    assert "private provider detail" not in str(raised.value)
