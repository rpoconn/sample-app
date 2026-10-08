from pathlib import Path
from typing import Any

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.errors import ApiError

FRONTEND_DIR = Path(__file__).parent / "frontend"


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_HOST],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def error_response(
    status_code: int,
    detail: str,
    code: str,
    context: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """The one error body: {detail, code, context}."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "code": code, "context": context or {}},
        headers=headers,
    )


@app.exception_handler(ApiError)
def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        exc.status_code, exc.detail, exc.code, exc.context, exc.headers
    )


# Routing 404s / 405s, and anything else raised as a Starlette HTTPException
@app.exception_handler(StarletteHTTPException)
def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 401 comes from OAuth2PasswordBearer when the Authorization header is missing
    code = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}.get(
        exc.status_code, f"http_{exc.status_code}"
    )
    return error_response(
        exc.status_code, str(exc.detail), code, headers=getattr(exc, "headers", None)
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = jsonable_encoder(exc.errors())
    detail = errors[0]["msg"] if errors else "Invalid input"
    return error_response(422, detail, "invalid_input", {"errors": errors})


app.include_router(api_router, prefix=settings.API_V1_STR)
# The built frontend only exists in the Docker image; locally, Vite serves it
if FRONTEND_DIR.is_dir():
    app.frontend("/", directory=FRONTEND_DIR)
