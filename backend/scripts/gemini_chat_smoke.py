import argparse
from getpass import getpass
from pathlib import Path

import httpx


_NO_CONTEXT_ANSWER = "I could not find this in your documents."


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
                print("Login failed; check the account and API response.")
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
                print(f"PDF upload failed with HTTP {upload.status_code}.")
                return 1

            document = upload.json()
            if document["status"] != "ready":
                print("PDF embeddings are not ready; check the document status.")
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
                error = response.json().get("error", {})
                if error.get("code") == "CHAT_MODEL_NOT_FOUND":
                    print(
                        "Gemini returned 404 for GEMINI_CHAT_MODEL. "
                        "Set GEMINI_CHAT_MODEL to a model available to your API key."
                    )
                elif error.get("code") == "CHAT_QUOTA_EXCEEDED":
                    print("Gemini quota was reached; try again in a minute.")
                else:
                    print(f"Chat smoke test failed with HTTP {response.status_code}.")
                return 1

            result = response.json()
            if (
                result["answer"] == _NO_CONTEXT_ANSWER
                or not result["citations"]
            ):
                print(
                    "No cited answer was produced, so Gemini may not have been "
                    "called. Try a question matching the PDF text."
                )
                return 1

            print(
                "Gemini chat call succeeded with "
                f"{len(result['citations'])} validated citation(s)."
            )
    except httpx.HTTPError:
        print("Could not reach the local API; no connection details were logged.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
