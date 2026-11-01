from app.ai.interfaces import EmbeddingClient, LLMClient
from app.core.constants import EMBEDDING_DIMENSION


class FakeLLMClient(LLMClient):
    def __init__(self, response: str = "fake response") -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
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
