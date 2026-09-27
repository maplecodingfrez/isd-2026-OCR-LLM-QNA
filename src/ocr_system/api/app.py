"""FastAPI Application factory for OCR System REST API.

Configures:
- OpenAPI / Swagger documentation (/docs, /redoc)
- CORS middleware
- Custom exception handlers matching ISD Chapter 10 slide 16
"""

from http import HTTPStatus
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .routes import router


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    app = FastAPI(
        title=settings.title,
        version=settings.version,
        description=settings.description,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    # CORS configuration (Chapter 10 slide 23)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Standardized error responses (Chapter 10 slide 16)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        try:
            status_phrase = HTTPStatus(exc.status_code).phrase.replace(" ", "")
        except ValueError:
            status_phrase = "HttpError"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": exc.status_code,
                "error": status_phrase,
                "message": exc.detail,
                "detail": None,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "status": 422,
                "error": "ValidationError",
                "message": "Input validation failed for request parameters or body",
                "detail": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "status": 500,
                "error": "InternalServerError",
                "message": str(exc) or "An unexpected server error occurred",
                "detail": None,
            },
        )

    app.include_router(router)
    return app


app = create_app()
