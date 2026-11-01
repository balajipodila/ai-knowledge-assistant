from fastapi import FastAPI, Request

from app.api.router import api_router
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, create_request_id


def create_app() -> FastAPI:
    configure_logging()
    application = FastAPI(title="AI Knowledge Assistant API")
    register_exception_handlers(application)
    application.include_router(api_router)

    @application.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = create_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    return application


app = create_app()
