import hashlib
import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

import structlog
from app.ai.interfaces import EmbeddingClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.demo import max_documents_per_user, max_pdf_pages
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.services.chunking import chunk_text
from app.services.embeddings import EmbeddingService
from app.services.pdf_extraction import PDFExtractionError, PDFTextExtractor
from app.services.storage import FileStorage

_PDF_CONTENT_TYPE = "application/pdf"
_MAX_DISPLAY_FILENAME_LENGTH = 512
logger = structlog.get_logger(__name__)


class DocumentUploadError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def sanitize_filename(filename: str | None) -> str:
    raw_name = (filename or "").replace("\x00", "")
    basename = PureWindowsPath(raw_name).name
    basename = PurePosixPath(basename).name
    normalized = unicodedata.normalize("NFKC", basename)
    safe_name = re.sub(r"[^\w.-]+", "_", normalized, flags=re.UNICODE)
    safe_name = safe_name.strip("._")
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name or 'document'}.pdf"
    return safe_name[:_MAX_DISPLAY_FILENAME_LENGTH]


class DocumentIngestionService:
    def __init__(
        self,
        *,
        storage: FileStorage,
        settings: Settings,
        embedding_client: EmbeddingClient,
        extractor: PDFTextExtractor | None = None,
    ) -> None:
        self.storage = storage
        self.settings = settings
        self.extractor = extractor or PDFTextExtractor()
        self.embedding_service = EmbeddingService(
            client=embedding_client,
            settings=settings,
        )

    def upload(
        self,
        session: Session,
        *,
        user: User,
        filename: str | None,
        content_type: str | None,
        data: bytes,
    ) -> tuple[Document, int, bool]:
        display_name = sanitize_filename(filename)
        if not filename or PureWindowsPath(filename).suffix.lower() != ".pdf":
            raise DocumentUploadError(
                415, "UNSUPPORTED_FILE_EXTENSION", "Only .pdf files are accepted."
            )
        if content_type != _PDF_CONTENT_TYPE:
            raise DocumentUploadError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "The uploaded file must have content type application/pdf.",
            )
        if not data:
            raise DocumentUploadError(422, "EMPTY_FILE", "The uploaded file is empty.")
        if len(data) > self.settings.max_upload_size_bytes:
            raise DocumentUploadError(
                413,
                "FILE_TOO_LARGE",
                "The uploaded file exceeds the configured size limit.",
            )
        if not data.startswith(b"%PDF-"):
            raise DocumentUploadError(
                422,
                "INVALID_PDF_SIGNATURE",
                "The file does not have a valid PDF signature.",
            )

        content_hash = hashlib.sha256(data).hexdigest()
        session.execute(
            select(User.id).where(User.id == user.id).with_for_update()
        ).scalar_one()
        existing = session.scalar(
            select(Document).where(
                Document.user_id == user.id,
                Document.content_hash == content_hash,
            )
        )
        if existing is not None:
            return existing, len(existing.chunks), True

        document_count = session.scalar(
            select(func.count(Document.id)).where(Document.user_id == user.id)
        )
        total_document_count = session.scalar(select(func.count(Document.id)))
        if self.settings.demo_mode and (total_document_count or 0) >= self.settings.demo_max_documents:
            raise DocumentUploadError(
                409,
                "DEMO_DOCUMENT_LIMIT_REACHED",
                "The public demo has reached its document limit. Please try again later.",
            )
        if (document_count or 0) >= max_documents_per_user(self.settings):
            raise DocumentUploadError(
                409,
                "DOCUMENT_LIMIT_REACHED",
                "You have reached the maximum number of documents for this account.",
            )

        storage_key = self.storage.save(data)
        document = Document(
            user_id=user.id,
            filename=display_name,
            content_type=content_type,
            content_hash=content_hash,
            page_count=0,
            status="processing",
            storage_key=storage_key,
        )
        session.add(document)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            self.storage.delete(storage_key)
            duplicate = session.scalar(
                select(Document).where(
                    Document.user_id == user.id,
                    Document.content_hash == content_hash,
                )
            )
            if duplicate is not None:
                return duplicate, len(duplicate.chunks), True
            raise
        except Exception:
            session.rollback()
            self.storage.delete(storage_key)
            raise

        try:
            pages = self.extractor.extract(
                data, max_pages=max_pdf_pages(self.settings)
            )
        except PDFExtractionError as error:
            document.status = "failed"
            document.failure_reason = error.message
            document.page_count = error.page_count
            session.commit()
            raise DocumentUploadError(
                error.status_code, error.code, error.message
            ) from None

        try:
            chunks: list[Chunk] = []
            chunk_index = 0
            for page in pages:
                page_chunks = chunk_text(
                    page.text,
                    chunk_size=self.settings.chunk_size,
                    overlap=self.settings.chunk_overlap,
                )
                for text in page_chunks:
                    chunks.append(
                        Chunk(
                            user_id=user.id,
                            document_id=document.id,
                            page_number=page.page_number,
                            chunk_index=chunk_index,
                            content=text,
                            metadata_json={},
                            embedding=None,
                        )
                    )
                    chunk_index += 1
            session.add_all(chunks)
            document.page_count = len(pages)
            document.status = "processing"
            session.commit()
        except Exception as error:
            session.rollback()
            failed_document = session.get(Document, document.id)
            if failed_document is not None:
                failed_document.status = "failed"
                failed_document.failure_reason = (
                    "Document ingestion could not be completed."
                )
                session.commit()
            logger.error(
                "Document ingestion failed",
                document_id=str(document.id),
                exception_type=type(error).__name__,
            )
            raise
        embedded_document = self.embedding_service.embed_document(
            session,
            document_id=document.id,
            user_id=user.id,
        )
        if embedded_document is None:
            raise RuntimeError("The uploaded document disappeared during embedding.")
        return embedded_document, len(chunks), False
