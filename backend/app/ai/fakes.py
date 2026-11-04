from collections.abc import Sequence

from app.ai.interfaces import EmbeddingClient, LLMClient
from app.core.constants import EMBEDDING_DIMENSION


class FakeLLMClient(LLMClient):
    def __init__(
        self,
        response: str = "fake response",
        *,
        responses: Sequence[str | Exception] = (),
    ) -> None:
        self.response = response
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.system_instructions: list[str] = []
        self.calls: list[dict[str, str | float | None]] = []

    def generate(
        self,
        prompt: str,
        *,
        system_instruction: str = "",
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> str:
        self.prompts.append(prompt)
        self.system_instructions.append(system_instruction)
        self.calls.append(
            {
                "model": model,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return self.response


class FakeEmbeddingClient(EmbeddingClient):
    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        if dimension < 1:
            raise ValueError("Embedding dimension must be positive.")
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        seed = sum(text.encode("utf-8"))
        return [float((seed + index) % 101) / 100 for index in range(self.dimension)]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]
