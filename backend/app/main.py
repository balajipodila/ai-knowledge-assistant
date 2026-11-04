from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_id import REQUEST_ID_HEADER, create_request_id
from app.core.tokens import validate_jwt_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        validate_jwt_settings(settings or get_settings())
        yield

    application = FastAPI(title="AI Knowledge Assistant API", lifespan=lifespan)
    cors_settings = settings or get_settings()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=[REQUEST_ID_HEADER],
    )
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
