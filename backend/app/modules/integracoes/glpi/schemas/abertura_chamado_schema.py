"""Schemas do fluxo generico de abertura de chamado GLPI."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AbrirChamadoGlpiRequest(BaseModel):
    origem_modulo: str = Field(min_length=1, max_length=80)
    origem_entidade: str = Field(min_length=1, max_length=80)
    origem_entidade_id: str = Field(min_length=1, max_length=120)
    tipo_evento: str = Field(min_length=1, max_length=120)
    titulo: str = Field(min_length=1, max_length=255)
    descricao: str = Field(min_length=1)
    categoria_id: int | None = None
    localizacao_id: int | None = None
    urgency: int | None = None
    requester_user_id: int | None = None
    assign_user_id: int | None = None
    assign_group_id: int | None = None
    hash_deduplicacao: str = Field(min_length=1, max_length=255)
    metadados: dict[str, Any] = Field(default_factory=dict)


class ResultadoAberturaGlpi(BaseModel):
    registro_id: int
    status_integracao: str
    glpi_ticket_id: int | None = None
    duplicado: bool = False
    erro: str | None = None
