import argparse
from getpass import getpass
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload a sample PDF and smoke-test Gemini-backed search."
    )
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    arguments = parser.parse_args()

    if not arguments.pdf.is_file() or arguments.pdf.suffix.lower() != ".pdf":
        print("Provide an existing sample PDF file.")
        return 2

    email = input("Account email: ").strip()
    password = getpass("Account password: ")
    query = input("Search query: ").strip()
    if not email or not password or not query:
        print("Email, password, and query are required.")
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
                print(f"Upload failed with HTTP {upload.status_code}.")
                return 1

            document = upload.json()
            print(
                f"Upload status: {document['status']} "
                f"(document {document['id']}, {document['chunk_count']} chunks)"
            )
            if document["status"] != "ready":
                print("Embeddings are not ready; check the document status and retry.")
                return 1

            response = client.post(
                "/search",
                headers=headers,
                json={"query": query, "top_k": 5},
            )
            if response.status_code != 200:
                print(f"Search failed with HTTP {response.status_code}.")
                return 1
            results = response.json()["results"]
            print(f"Search returned {len(results)} result(s).")
            for result in results:
                print(
                    f"{result['filename']} page {result['page_number']} "
                    f"(similarity {result['similarity_score']:.3f})"
                )
    except httpx.HTTPError:
        print("Could not reach the local API; no connection details were logged.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
