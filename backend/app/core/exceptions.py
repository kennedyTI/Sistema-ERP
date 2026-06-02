"""
Handlers HTTP padronizados da API.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.response import api_error


async def http_exception_handler(request: Request, exc: Exception):  # noqa: ARG001
    if isinstance(exc, StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=api_error(detail),
            headers=getattr(exc, "headers", None),
        )

    return JSONResponse(status_code=500, content=api_error("Erro interno do servidor"))


async def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
    errors = [str(error.get("msg", error)) for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=api_error("Erro de validacao da requisicao", errors),
    )
