import argparse
from getpass import getpass
from pathlib import Path

import httpx


_NO_CONTEXT_ANSWER = "I could not find this in your documents."


def _request_id(response: httpx.Response) -> str:
    if request_id := response.headers.get("X-Request-ID"):
        return request_id
    try:
        body = response.json()
    except ValueError:
        return "unavailable"
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and isinstance(error.get("request_id"), str):
            return error["request_id"]
    return "unavailable"


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


def _print_failure(response: httpx.Response, message: str) -> None:
    print(f"{message} HTTP {response.status_code}.")
    print(f"Error code: {_error_code(response)}")
    print(f"Request ID: {_request_id(response)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke-test cited chat with a synthetic PDF and Gemini."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    arguments = parser.parse_args()

    if not arguments.pdf.is_file() or arguments.pdf.suffix.lower() != ".pdf":
        print("Provide an existing sample PDF file.")
        return 2

    email = input("Account email: ").strip()
    password = getpass("Account password: ")
    question = input("Question answered by the PDF: ").strip()
    if not email or not password or not question:
        print("Email, password, and question are required.")
        return 2

    try:
        with httpx.Client(base_url=arguments.base_url.rstrip("/"), timeout=90) as client:
            login = client.post(
                "/auth/login",
                json={"email": email, "password": password},
            )
            if login.status_code != 200:
                _print_failure(login, "Login failed; check the account.")
                return 1
            token = login.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            with arguments.pdf.open("rb") as pdf_file:
                upload = client.post(
                    "/documents",
                    headers=headers,
                    files={
                        "file": (
                            arguments.pdf.name,
                            pdf_file,
                            "application/pdf",
                        )
                    },
                )
            if upload.status_code not in {200, 201}:
                _print_failure(upload, "PDF upload failed.")
                return 1

            document = upload.json()
            if document["status"] != "ready":
                print(
                    f"PDF embeddings are not ready. HTTP {upload.status_code}. "
                    f"Request ID: {_request_id(upload)}"
                )
                return 1

            response = client.post(
                "/chat",
                headers=headers,
                json={
                    "question": question,
                    "document_ids": [document["id"]],
                },
            )
            if response.status_code != 200:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                error = body.get("error", {}) if isinstance(body, dict) else {}
                if not isinstance(error, dict):
                    error = {}
                message = "Chat request failed."
                if error.get("code") == "CHAT_MODEL_NOT_FOUND":
                    message = (
                        "Gemini returned 404 for GEMINI_CHAT_MODEL. "
                        "Set GEMINI_CHAT_MODEL to a model available to your API key."
                    )
                elif error.get("code") == "CHAT_QUOTA_EXCEEDED":
                    message = "Gemini quota was reached; try again in a minute."
                elif error.get("code") == "CHAT_SEARCH_UNAVAILABLE":
                    message = (
                        "Question embedding failed; document search is unavailable."
                    )
                elif error.get("code") == "CHAT_UNAVAILABLE":
                    message = "Gemini answer generation is temporarily unavailable."
                _print_failure(response, message)
                return 1

            result = response.json()
            print(f"HTTP status: {response.status_code}")
            print("Answer:")
            print(result["answer"])
            print("Citations:")
            citations = result.get("citations", [])
            if not citations:
                print("  (none)")
                if result["answer"] == _NO_CONTEXT_ANSWER:
                    print(
                        "No matching context was found; the fixed fallback was "
                        "returned without an LLM answer."
                    )
                return 1
            for citation in citations:
                snippet = " ".join(citation["snippet"].split())
                if len(snippet) > 200:
                    snippet = f"{snippet[:197]}..."
                print(
                    f"  [{citation['number']}] {citation['filename']} "
                    f"page {citation['page_number']}: {snippet}"
                )
    except httpx.HTTPError:
        print("Could not reach the local API; no connection details were logged.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
