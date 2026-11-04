import argparse
from getpass import getpass
from pathlib import Path
from uuid import UUID

import httpx


_QUESTION_LABELS = ("relevant", "offtopic")
_TOP_K = 5


def _read_questions(path: Path) -> list[tuple[str, str]]:
    questions: list[tuple[str, str]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line:
            continue
        label, separator, question = line.partition(":")
        normalized_label = label.strip().lower()
        question = question.strip()
        if (
            not separator
            or normalized_label not in _QUESTION_LABELS
            or not question
        ):
            raise ValueError(
                f"Invalid question file entry at line {line_number}; "
                "use 'relevant: question' or 'offtopic: question'."
            )
        questions.append((normalized_label, question))
    if not questions:
        raise ValueError("The question file contains no labelled questions.")
    return questions


def _error_code(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return "unavailable"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("code"), str):
            return error["code"]
    return "unavailable"


def _print_ranges(scores: dict[str, list[float]]) -> None:
    print("Top-1 similarity ranges:")
    for label in _QUESTION_LABELS:
        values = scores[label]
        if values:
            print(f"  {label}: min={min(values):.4f}, max={max(values):.4f}")
        else:
            print(f"  {label}: no results")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure top-5 similarity scores for relevant and off-topic "
            "questions against one document."
        )
    )
    parser.add_argument("--document-id", required=True, type=UUID)
    parser.add_argument("--questions-file", required=True, type=Path)
    parser.add_argument("--base-url", default="http://localhost:8000")
    arguments = parser.parse_args()

    try:
        questions = _read_questions(arguments.questions_file)
    except (OSError, UnicodeError):
        print("Could not read the questions file.")
        return 2
    except ValueError as error:
        print(f"Could not read questions: {error}")
        return 2

    email = input("Account email: ").strip()
    password = getpass("Account password: ")
    if not email or not password:
        print("Email and password are required.")
        return 2

    top1_scores: dict[str, list[float]] = {
        label: [] for label in _QUESTION_LABELS
    }

    try:
        with httpx.Client(
            base_url=arguments.base_url.rstrip("/"),
            timeout=90,
        ) as client:
            login = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            if login.status_code != 200:
                print(
                    f"Login failed (HTTP {login.status_code}, "
                    f"error code {_error_code(login)})."
                )
                return 1
            token = login.json()["access_token"]
            headers = {"Authorization": "Bearer " + token}

            for index, (label, question) in enumerate(questions, start=1):
                response = client.post(
                    "/search",
                    headers=headers,
                    json={
                        "query": question,
                        "top_k": _TOP_K,
                        "document_ids": [str(arguments.document_id)],
                        "min_similarity": -1.0,
                    },
                )
                if response.status_code != 200:
                    print(
                        f"Question {index} ({label}) failed: "
                        f"HTTP {response.status_code}, "
                        f"error code {_error_code(response)}."
                    )
                    return 1

                results = response.json()["results"]
                print(f"Question {index} ({label}):")
                if not results:
                    print("  no matching chunks")
                    continue
                top1_scores[label].append(results[0]["similarity_score"])
                for result in results[:_TOP_K]:
                    print(
                        f"  score={result['similarity_score']:.4f}, "
                        f"page={result['page_number']}"
                    )
    except httpx.HTTPError:
        print("Could not reach the local API; no connection details were logged.")
        return 1
    except (KeyError, TypeError, ValueError):
        print("The API returned an unexpected response; no response data was logged.")
        return 1

    _print_ranges(top1_scores)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
