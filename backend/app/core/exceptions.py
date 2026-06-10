"""
Handlers HTTP padronizados da API.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.response import api_error


def _is_machines_v2(request: Request) -> bool:
    return request.url.path.startswith("/api/v2/printers/machines")


def _machine_error(message: str, errors: dict[str, list[str]] | None = None) -> dict:
    return {
        "sucesso": False,
        "mensagem": message,
        "dados": None,
        "erros": errors or {"geral": [message]},
    }


async def http_exception_handler(request: Request, exc: Exception):  # noqa: ARG001
    if isinstance(exc, StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        if _is_machines_v2(request):
            return JSONResponse(
                status_code=exc.status_code,
                content=_machine_error(detail),
                headers=getattr(exc, "headers", None),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=api_error(detail),
            headers=getattr(exc, "headers", None),
        )

    return JSONResponse(status_code=500, content=api_error("Erro interno do servidor"))


async def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
    if _is_machines_v2(request):
        field_errors: dict[str, list[str]] = {}
        for error in exc.errors():
            location = error.get("loc", ())
            field = str(location[-1]) if location else "geral"
            message = str(error.get("msg", "Valor invalido."))
            if message.startswith("Value error, "):
                message = message.removeprefix("Value error, ")
            field_errors.setdefault(field, []).append(message)
        return JSONResponse(
            status_code=422,
            content=_machine_error(
                "Nao foi possivel validar os dados da maquina.",
                field_errors,
            ),
        )
    errors = [str(error.get("msg", error)) for error in exc.errors()]
    return JSONResponse(
        status_code=422,
        content=api_error("Erro de validacao da requisicao", errors),
    )
