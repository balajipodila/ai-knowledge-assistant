from collections.abc import Generator
from io import BytesIO
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai.dependencies import get_embedding_client
from app.ai.errors import EmbeddingProviderError
from app.ai.fakes import FakeEmbeddingClient
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.passwords import hash_password
from app.core.tokens import create_access_token
from app.main import create_app
from app.models import Base, Chunk, Document, EmbeddingCache, User
from app.services.storage import FileStorage

_TEST_SECRET = "test-only-signing-key-with-at-least-32-bytes"


def _pdf_bytes(pages: list[str | None]) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in pages:
        if text:
            pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


@pytest.fixture
def document_client(tmp_path: Path) -> Generator[dict[str, Any], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        user = User(
            email="owner@example.com",
            password_hash=hash_password("test password"),
        )
        session.add(user)
        session.commit()
        owner_id = user.id

    settings = Settings.model_validate(
        {
            "jwt_secret_key": _TEST_SECRET,
            "upload_directory": tmp_path / "uploads",
            "max_upload_size_bytes": 4096,
            "max_pdf_pages": 2,
            "chunk_size": 180,
            "chunk_overlap": 30,
        }
    )
    application = create_app(settings=settings)

    def override_db() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    application.dependency_overrides[get_db] = override_db
    application.dependency_overrides[get_settings] = lambda: settings
    embedding_client = FakeEmbeddingClient()
    application.dependency_overrides[get_embedding_client] = lambda: embedding_client
    token = create_access_token(owner_id, settings)
    try:
        with TestClient(application) as client:
            yield {
                "client": client,
                "headers": {"Authorization": f"Bearer {token}"},
                "factory": factory,
                "owner_id": owner_id,
                "settings": settings,
                "embedding_client": embedding_client,
                "application": application,
            }
    finally:
        application.dependency_overrides.clear()
        engine.dispose()


def _upload(
    context: dict[str, Any],
    content: bytes,
    *,
    filename: str = "sample.pdf",
    content_type: str = "application/pdf",
) -> Any:
    return context["client"].post(
        "/documents",
        files={"file": (filename, content, content_type)},
        headers=context["headers"],
    )


def test_valid_upload_extracts_text_and_stores_page_chunks(
    document_client: dict[str, Any],
) -> None:
    content = _pdf_bytes(
        [
            "First page. " + "This is a repeated sentence for chunk boundary testing. " * 12,
            "Second page has its own text.",
        ]
    )

    response = _upload(document_client, content, filename=r"C:\unsafe\sample.pdf")

    assert response.status_code == 201
    payload = response.json()
    document_id = UUID(payload["id"])
    assert payload["filename"] == "sample.pdf"
    assert payload["status"] == "ready"
    assert payload["page_count"] == 2
    assert payload["chunk_count"] > 1
    assert payload["duplicate"] is False
    own_document = document_client["client"].get(
        f"/documents/{payload['id']}", headers=document_client["headers"]
    )
    assert own_document.status_code == 200
    assert own_document.json()["id"] == payload["id"]

    with document_client["factory"]() as session:
        chunks = session.scalars(
            select(Chunk).where(Chunk.document_id == document_id)
        ).all()
        document = session.get(Document, document_id)
    assert document.content_hash
    assert document.storage_key
    assert all(chunk.embedding is not None for chunk in chunks)
    assert all(
        chunk.embedding_model == document_client["settings"].gemini_embedding_model
        for chunk in chunks
    )
    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert all(len(chunk.content) <= 180 for chunk in chunks)
    assert (document_client["settings"].upload_directory / document.storage_key).exists()


def test_upload_and_delete_use_the_configured_storage_factory(
    document_client: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MemoryFileStorage(FileStorage):
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def save(self, data: bytes) -> str:
            key = "stored.pdf"
            self.objects[key] = data
            return key

        def delete(self, storage_key: str) -> None:
            del self.objects[storage_key]

    storage = MemoryFileStorage()
    monkeypatch.setattr(
        "app.api.documents.create_file_storage",
        lambda settings: storage,
    )
    content = _pdf_bytes(["Storage factory test"])
    upload = _upload(document_client, content)

    assert upload.status_code == 201
    document_id = upload.json()["id"]
    assert storage.objects == {"stored.pdf": content}

    delete = document_client["client"].delete(
        f"/documents/{document_id}",
        headers=document_client["headers"],
    )

    assert delete.status_code == 204
    assert storage.objects == {}


def test_document_cap_allows_duplicate_but_rejects_a_new_document(
    document_client: dict[str, Any],
) -> None:
    document_client["settings"].max_documents_per_user = 1
    first_pdf = _pdf_bytes(["First document contents."])
    second_pdf = _pdf_bytes(["Different document contents."])

    first = _upload(document_client, first_pdf, filename="first.pdf")
    duplicate = _upload(document_client, first_pdf, filename="first-copy.pdf")
    over_limit = _upload(document_client, second_pdf, filename="second.pdf")

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert over_limit.status_code == 409
    assert over_limit.json()["error"]["code"] == "DOCUMENT_LIMIT_REACHED"


def test_demo_user_cannot_upload_or_delete_documents(
    document_client: dict[str, Any],
) -> None:
    settings = document_client["settings"]
    settings.demo_mode = True
    with document_client["factory"]() as session:
        demo_user = User(
            email=settings.demo_user_email,
            password_hash="not-a-login-password",
        )
        session.add(demo_user)
        session.commit()
        demo_document = Document(
            user_id=demo_user.id,
            filename="seed.pdf",
            content_hash="a" * 64,
            page_count=1,
            status="ready",
        )
        session.add(demo_document)
        session.commit()
        token = create_access_token(demo_user.id, settings)

    headers = {"Authorization": f"Bearer {token}"}
    upload = document_client["client"].post(
        "/documents",
        files={"file": ("new.pdf", b"%PDF-1.7", "application/pdf")},
        headers=headers,
    )
    delete = document_client["client"].delete(
        f"/documents/{demo_document.id}",
        headers=headers,
    )

    assert upload.status_code == 403
    assert delete.status_code == 403
    assert delete.json()["error"]["code"] == "FORBIDDEN"


def test_demo_user_cannot_read_another_users_documents(
    document_client: dict[str, Any],
) -> None:
    settings = document_client["settings"]
    settings.demo_mode = True
    with document_client["factory"]() as session:
        demo_user = User(
            email=settings.demo_user_email,
            password_hash="not-a-login-password",
        )
        other_user = User(email="other@example.com", password_hash="test-hash")
        session.add_all([demo_user, other_user])
        session.commit()
        own_document = Document(
            user_id=demo_user.id,
            filename="seed.pdf",
            content_hash="b" * 64,
            page_count=1,
            status="ready",
        )
        other_document = Document(
            user_id=other_user.id,
            filename="private.pdf",
            content_hash="c" * 64,
            page_count=1,
            status="ready",
        )
        session.add_all([own_document, other_document])
        session.commit()
        token = create_access_token(
            demo_user.id,
            settings,
            is_demo=True,
            rate_limit_identity="demo:test-session",
        )

    headers = {"Authorization": f"Bearer {token}"}
    listed = document_client["client"].get("/documents", headers=headers)
    hidden = document_client["client"].get(
        f"/documents/{other_document.id}", headers=headers
    )

    assert [item["id"] for item in listed.json()] == [str(own_document.id)]
    assert hidden.status_code == 404


def test_ai_feature_switch_blocks_upload_before_ingestion(
    document_client: dict[str, Any],
) -> None:
    document_client["settings"].ai_features_enabled = False

    response = _upload(document_client, b"%PDF-1.7")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "expected_code"),
    [
        ("report.txt", "application/pdf", b"%PDF-1.4", "UNSUPPORTED_FILE_EXTENSION"),
        ("report.pdf", "text/plain", b"%PDF-1.4", "UNSUPPORTED_MEDIA_TYPE"),
        ("fake.pdf", "application/pdf", b"not a pdf", "INVALID_PDF_SIGNATURE"),
        ("empty.pdf", "application/pdf", b"", "EMPTY_FILE"),
        (
            "oversized.pdf",
            "application/pdf",
            b"%PDF-1.4" + (b"x" * 4090),
            "FILE_TOO_LARGE",
        ),
    ],
)
def test_upload_validation_rejects_bad_file_inputs(
    document_client: dict[str, Any],
    filename: str,
    content_type: str,
    content: bytes,
    expected_code: str,
) -> None:
    response = _upload(
        document_client, content, filename=filename, content_type=content_type
    )

    assert response.status_code in {413, 415, 422}
    assert response.json()["error"]["code"] == expected_code


def test_corrupt_pdf_returns_clean_error_not_server_error(
    document_client: dict[str, Any],
) -> None:
    response = _upload(
        document_client,
        b"%PDF-1.7\nthis is not a valid PDF object structure",
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_INVALID"
    assert "Traceback" not in response.text
    with document_client["factory"]() as session:
        document = session.scalar(
            select(Document).where(Document.status == "failed")
        )
    assert document is not None
    assert document.failure_reason == "The uploaded file is not a readable PDF."
    assert document.storage_key is not None


def test_scanned_pdf_is_recorded_as_failed_with_clear_reason(
    document_client: dict[str, Any],
) -> None:
    response = _upload(document_client, _pdf_bytes([None]))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_NO_TEXT"
    assert "OCR" in response.json()["error"]["message"]
    with document_client["factory"]() as session:
        document = session.scalar(
            select(Document).where(Document.status == "failed")
        )
    assert document is not None
    assert document.failure_reason is not None
    assert document.page_count == 1
    assert document.storage_key is not None
    assert (document_client["settings"].upload_directory / document.storage_key).exists()


def test_page_limit_is_enforced(document_client: dict[str, Any]) -> None:
    response = _upload(document_client, _pdf_bytes(["one", "two", "three"]))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_TOO_MANY_PAGES"
    with document_client["factory"]() as session:
        document = session.scalar(
            select(Document).where(Document.status == "failed")
        )
    assert document is not None
    assert document.page_count == 3


def test_demo_page_limit_is_lower_and_configurable(
    document_client: dict[str, Any],
) -> None:
    document_client["settings"].demo_mode = True
    document_client["settings"].demo_max_pdf_pages = 1
    response = _upload(document_client, _pdf_bytes(["one", "two"]))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_TOO_MANY_PAGES"


def test_duplicate_upload_returns_existing_document(
    document_client: dict[str, Any],
) -> None:
    content = _pdf_bytes(["Repeated upload content"])
    first = _upload(document_client, content)
    second = _upload(document_client, content)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    files = list(document_client["settings"].upload_directory.glob("*.pdf"))
    assert len(files) == 1


def test_embedding_failure_preserves_upload_and_retry_completes_it(
    document_client: dict[str, Any],
) -> None:
    document_client["settings"].embedding_max_attempts = 1

    class UnavailableEmbeddingClient(FakeEmbeddingClient):
        def embed_many(self, texts: list[str]) -> list[list[float]]:
            del texts
            raise EmbeddingProviderError(
                "Gemini embedding service is temporarily unavailable.",
                retryable=True,
            )

    document_client["application"].dependency_overrides[get_embedding_client] = (
        UnavailableEmbeddingClient
    )
    response = _upload(document_client, _pdf_bytes(["Keep this upload."]))

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "embedding_failed"
    assert payload["failure_reason"] == (
        "Gemini embedding service is temporarily unavailable."
    )
    document_id = UUID(payload["id"])
    with document_client["factory"]() as session:
        chunks = session.scalars(
            select(Chunk).where(Chunk.document_id == document_id)
        ).all()
        document = session.get(Document, document_id)
    assert len(chunks) == payload["chunk_count"]
    assert all(chunk.embedding is None for chunk in chunks)
    assert document is not None
    assert document.storage_key is not None
    assert (document_client["settings"].upload_directory / document.storage_key).exists()

    document_client["application"].dependency_overrides[get_embedding_client] = (
        lambda: document_client["embedding_client"]
    )
    retry = document_client["client"].post(
        f"/documents/{document_id}/retry-embedding",
        headers=document_client["headers"],
    )
    assert retry.status_code == 200
    assert retry.json()["status"] == "ready"


def test_listing_only_returns_the_current_users_documents(
    document_client: dict[str, Any],
) -> None:
    _upload(document_client, _pdf_bytes(["Owner document"]))
    with document_client["factory"]() as session:
        other_user = User(
            email="other@example.com",
            password_hash=hash_password("test password"),
        )
        session.add(other_user)
        session.flush()
        session.add(
            Document(
                user_id=other_user.id,
                filename="other.pdf",
                content_hash="a" * 64,
                page_count=1,
                status="ready",
            )
        )
        session.commit()

    response = document_client["client"].get(
        "/documents", headers=document_client["headers"]
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["filename"] == "sample.pdf"


def test_another_users_document_is_404_for_get_and_delete(
    document_client: dict[str, Any],
) -> None:
    with document_client["factory"]() as session:
        other_user = User(
            email="other@example.com",
            password_hash=hash_password("test password"),
        )
        session.add(other_user)
        session.flush()
        document = Document(
            user_id=other_user.id,
            filename="private.pdf",
            content_hash="b" * 64,
            page_count=1,
            status="ready",
        )
        session.add(document)
        session.commit()
        document_id = document.id

    get_response = document_client["client"].get(
        f"/documents/{document_id}", headers=document_client["headers"]
    )
    delete_response = document_client["client"].delete(
        f"/documents/{document_id}", headers=document_client["headers"]
    )

    assert get_response.status_code == 404
    assert delete_response.status_code == 404
    with document_client["factory"]() as session:
        assert session.get(Document, document_id) is not None


def test_delete_removes_document_chunks_and_stored_file(
    document_client: dict[str, Any],
) -> None:
    upload = _upload(document_client, _pdf_bytes(["Delete this document"]))
    document_id = UUID(upload.json()["id"])
    storage_key = None
    with document_client["factory"]() as session:
        document = session.get(Document, document_id)
        storage_key = document.storage_key

    response = document_client["client"].delete(
        f"/documents/{document_id}", headers=document_client["headers"]
    )

    assert response.status_code == 204
    assert not (document_client["settings"].upload_directory / storage_key).exists()
    with document_client["factory"]() as session:
        assert session.get(Document, document_id) is None
        assert session.scalars(
            select(Chunk).where(Chunk.document_id == document_id)
        ).all() == []
        assert session.scalar(
            select(EmbeddingCache).where(
                EmbeddingCache.user_id == document_client["owner_id"]
            )
        ) is None


def test_upload_requires_authentication(document_client: dict[str, Any]) -> None:
    response = document_client["client"].get("/documents")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_delete_succeeds_even_if_storage_delete_fails(
    document_client: dict[str, Any],
) -> None:
    upload = _upload(document_client, _pdf_bytes(["Delete with failing storage"]))
    document_id = UUID(upload.json()["id"])

    class DeleteFailingStorage(FileStorage):
        def save(self, data: bytes) -> str:
            return "dummy.pdf"
        def delete(self, storage_key: str) -> None:
            raise RuntimeError("Storage down")

    import app.api.documents as documents_api
    monkeypatch_storage = pytest.MonkeyPatch()
    monkeypatch_storage.setattr(documents_api, "create_file_storage", lambda s: DeleteFailingStorage())
    try:
        response = document_client["client"].delete(
            f"/documents/{document_id}",
            headers={**document_client["headers"], "X-Request-ID": "test-req-id-123"},
        )
        assert response.status_code == 204
        with document_client["factory"]() as session:
            assert session.get(Document, document_id) is None
    finally:
        monkeypatch_storage.undo()


def test_delete_is_idempotent_when_object_already_missing(
    document_client: dict[str, Any],
) -> None:
    upload = _upload(document_client, _pdf_bytes(["Delete missing object"]))
    document_id = UUID(upload.json()["id"])

    class MissingObjectStorage(FileStorage):
        def save(self, data: bytes) -> str:
            return "dummy.pdf"
        def delete(self, storage_key: str) -> None:
            raise FileNotFoundError("Object not found")

    import app.api.documents as documents_api
    monkeypatch_storage = pytest.MonkeyPatch()
    monkeypatch_storage.setattr(documents_api, "create_file_storage", lambda s: MissingObjectStorage())
    try:
        response = document_client["client"].delete(
            f"/documents/{document_id}",
            headers=document_client["headers"],
        )
        assert response.status_code == 204
        with document_client["factory"]() as session:
            assert session.get(Document, document_id) is None
    finally:
        monkeypatch_storage.undo()


def test_upload_fails_cleanly_when_storage_save_fails(
    document_client: dict[str, Any],
) -> None:
    class SaveFailingStorage(FileStorage):
        def save(self, data: bytes) -> str:
            raise RuntimeError("Storage save failed")
        def delete(self, storage_key: str) -> None:
            pass

    import app.api.documents as documents_api
    monkeypatch_storage = pytest.MonkeyPatch()
    monkeypatch_storage.setattr(documents_api, "create_file_storage", lambda s: SaveFailingStorage())
    try:
        pdf_content = _pdf_bytes(["Upload with save failure"])
        with pytest.raises(RuntimeError, match="Storage save failed"):
            document_client["client"].post(
                "/documents",
                headers=document_client["headers"],
                files={"file": ("sample.pdf", BytesIO(pdf_content), "application/pdf")},
            )
        with document_client["factory"]() as session:
            assert session.scalars(select(Document)).all() == []
    finally:
        monkeypatch_storage.undo()

