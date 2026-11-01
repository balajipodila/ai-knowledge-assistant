from dataclasses import dataclass
from io import BytesIO

import structlog
from pypdf import PdfReader

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


class PDFExtractionError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        page_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.page_count = page_count


class PDFTextExtractor:
    def extract(self, data: bytes, *, max_pages: int) -> list[ExtractedPage]:
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise PDFExtractionError(
                    "PDF_ENCRYPTED", "Password-protected PDFs are not supported."
                )
            page_count = len(reader.pages)
            if page_count == 0:
                raise PDFExtractionError("PDF_EMPTY", "The PDF contains no pages.")
            if page_count > max_pages:
                raise PDFExtractionError(
                    "PDF_TOO_MANY_PAGES",
                    f"The PDF exceeds the {max_pages}-page limit.",
                    page_count=page_count,
                )
            pages = [
                ExtractedPage(page_number=index, text=page.extract_text() or "")
                for index, page in enumerate(reader.pages, start=1)
            ]
        except PDFExtractionError:
            raise
        except Exception as error:
            logger.warning(
                "Rejected unreadable PDF",
                exception_type=type(error).__name__,
            )
            raise PDFExtractionError(
                "PDF_INVALID", "The uploaded file is not a readable PDF."
            ) from None

        if not any(page.text.strip() for page in pages):
            raise PDFExtractionError(
                "PDF_NO_TEXT",
                "No selectable text was found in the PDF. Scanned PDFs require OCR, "
                "which is not available yet.",
                page_count=len(pages),
            )
        return pages
