"""
Arquivo: backend/app/schemas/api_response.py

Descricao:
Contrato padrao de respostas da API operacional.

Formato:
- success: indica sucesso logico da chamada
- data: payload principal da rota
- message: mensagem curta para frontend/integracoes
- errors: lista de erros quando houver falha

Regra:
- APIs de leitura retornam sempre este envelope.
- Erros HTTP tambem seguem o mesmo envelope via exception handlers.
"""

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Envelope padrao para responses da API."""

    success: bool
    data: Optional[T] = None
    message: Optional[str] = None
    errors: Optional[list[str]] = None


class ApiErrorResponse(BaseModel):
    """Envelope padrao para erros da API."""

    success: bool = False
    data: None = None
    message: str
    errors: list[str] = Field(default_factory=list)


def api_success(data: T, message: str | None = None) -> dict:
    """Cria payload de sucesso no contrato padrao."""
    return {
        "success": True,
        "data": data,
        "message": message,
        "errors": None,
    }


def api_error(message: str, errors: list[str] | None = None) -> dict:
    """Cria payload de erro no contrato padrao."""
    return {
        "success": False,
        "data": None,
        "message": message,
        "errors": errors or [message],
    }
