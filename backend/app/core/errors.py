import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.core.request_id import get_request_id
from app.services.ingestion import DocumentUploadError

logger = structlog.get_logger(__name__)

_HTTP_MESSAGES = {
    400: ("BAD_REQUEST", "The request could not be processed."),
    401: ("UNAUTHORIZED", "Authentication is required."),
    403: ("FORBIDDEN", "The request is not permitted."),
    404: ("NOT_FOUND", "The requested resource was not found."),
    405: ("METHOD_NOT_ALLOWED", "The request method is not allowed."),
    409: ("CONFLICT", "The request conflicts with the current resource state."),
    413: ("PAYLOAD_TOO_LARGE", "The uploaded file exceeds the allowed size."),
    415: ("UNSUPPORTED_MEDIA_TYPE", "The uploaded file type is not supported."),
    429: ("TOO_MANY_REQUESTS", "Too many requests."),
    503: ("SERVICE_UNAVAILABLE", "The service is temporarily unavailable."),
    422: ("UNPROCESSABLE_ENTITY", "The request could not be processed."),
}


def _error_response(
    request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    request_id = get_request_id(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(DocumentUploadError)
    async def handle_document_upload_error(
        request: Request, exception: DocumentUploadError
    ) -> JSONResponse:
        return _error_response(
            request,
            exception.status_code,
            exception.code,
            exception.message,
        )

    @application.exception_handler(HTTPException)
    async def handle_http_exception(
        request: Request, exception: HTTPException
    ) -> JSONResponse:
        code, message = _HTTP_MESSAGES.get(
            exception.status_code, ("HTTP_ERROR", "The request failed.")
        )
        return _error_response(request, exception.status_code, code, message)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            422,
            "VALIDATION_ERROR",
            "Request validation failed.",
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request, exception: Exception
    ) -> JSONResponse:
        request_id = get_request_id(request)
        logger.error(
            "Unhandled request exception",
            request_id=request_id,
            exception_type=type(exception).__name__,
        )
        return _error_response(
            request,
            500,
            "INTERNAL_SERVER_ERROR",
            "An unexpected error occurred.",
        )
