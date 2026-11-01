from app.ai.fakes import FakeEmbeddingClient, FakeLLMClient
from app.ai.interfaces import EmbeddingClient, LLMClient


def test_fake_clients_implement_interfaces_and_return_deterministic_values() -> None:
    llm: LLMClient = FakeLLMClient("grounded answer")
    embeddings: EmbeddingClient = FakeEmbeddingClient(dimension=3)

    assert llm.generate("question") == "grounded answer"
    assert embeddings.embed("same input") == embeddings.embed("same input")
    assert len(embeddings.embed("same input")) == 3
    assert embeddings.embed_many(["a", "b"]) == [
        embeddings.embed("a"),
        embeddings.embed("b"),
    ]
