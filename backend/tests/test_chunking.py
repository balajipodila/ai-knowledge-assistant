import pytest

from app.services.chunking import chunk_text


def test_chunking_respects_size_and_keeps_sentence_overlap() -> None:
    sentence = "Sentence boundaries should remain readable."
    text = " ".join(f"{sentence} {index}." for index in range(12))

    chunks = chunk_text(text, chunk_size=100, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert any(
        set(previous.split()) & set(current.split())
        for previous, current in zip(chunks, chunks[1:])
    )


def test_chunking_splits_long_sentences_and_overlaps_content() -> None:
    text = " ".join(f"word{index}" for index in range(100))

    chunks = chunk_text(text, chunk_size=80, overlap=20)

    assert len(chunks) > 1
    assert all(len(chunk) <= 80 for chunk in chunks)
    assert any(
        set(previous.split()) & set(current.split())
        for previous, current in zip(chunks, chunks[1:])
    )


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (100, 100), (100, -1)],
)
def test_chunking_rejects_invalid_size_configuration(
    chunk_size: int, overlap: int
) -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=chunk_size, overlap=overlap)
