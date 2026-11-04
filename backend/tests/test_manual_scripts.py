from pathlib import Path

import httpx
import pytest

from scripts.gemini_chat_smoke import _print_failure
from scripts.retrieval_scores import _read_questions


def test_chat_smoke_failure_prints_error_code_and_request_id(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = httpx.Response(
        503,
        json={
            "error": {
                "code": "CHAT_SEARCH_UNAVAILABLE",
                "request_id": "request-123",
            }
        },
        headers={"X-Request-ID": "request-123"},
    )

    _print_failure(response, "Chat failed.")

    output = capsys.readouterr().out
    assert "HTTP 503" in output
    assert "CHAT_SEARCH_UNAVAILABLE" in output
    assert "request-123" in output


def test_retrieval_question_file_reads_labels_without_echoing_text(
    tmp_path: Path,
) -> None:
    path = tmp_path / "questions.txt"
    path.write_text(
        "relevant: What is machine learning?\nofftopic: Capital of Australia?\n",
        encoding="utf-8",
    )

    assert _read_questions(path) == [
        ("relevant", "What is machine learning?"),
        ("offtopic", "Capital of Australia?"),
    ]


def test_retrieval_question_file_rejects_unlabelled_questions(
    tmp_path: Path,
) -> None:
    path = tmp_path / "questions.txt"
    path.write_text("What is machine learning?\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        _read_questions(path)
