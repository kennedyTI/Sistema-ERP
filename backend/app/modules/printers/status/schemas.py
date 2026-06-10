"""Schemas da API de status operacional das impressoras."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


StatusOperacional = Literal["desconhecido", "online", "offline", "erro"]
NivelAlerta = Literal["cinza", "verde", "amarelo", "vermelho"]
OrigemStatus = Literal["sistema", "manual", "seed", "futuro_snmp"]


class PrinterStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    machine_id: int
    machine_name: str
    ip_address: str
    manufacturer: str | None = None
    model: str | None = None
    sector: str | None = None
    cost_center: str | None = None
    status_operacional: StatusOperacional
    nivel_alerta: NivelAlerta
    mensagem_alerta: str | None = None
    mensagem_operador: str
    ultima_verificacao_em: datetime | None = None
    ultimo_sucesso_em: datetime | None = None
    ultima_falha_em: datetime | None = None
    tempo_resposta_ms: int | None = None
    origem: OrigemStatus
    resposta_bruta: str | None = None


class PrinterStatusSummary(BaseModel):
    total_impressoras: int
    online: int
    offline: int
    com_alerta: int
    substituir_toner: int


class PrinterStatusUpdate(BaseModel):
    status_operacional: StatusOperacional
    nivel_alerta: NivelAlerta
    mensagem_alerta: str | None = Field(default=None, max_length=255)
    mensagem_operador: str | None = Field(default=None, min_length=1, max_length=255)
    tempo_resposta_ms: int | None = Field(default=None, ge=0)
    origem: OrigemStatus = "manual"
    resposta_bruta: str | None = None

    @field_validator("mensagem_alerta", "mensagem_operador", "resposta_bruta", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class PrinterLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    tipo_evento: str
    status_anterior: str | None = None
    status_novo: str | None = None
    alerta_anterior: str | None = None
    alerta_novo: str | None = None
    mensagem: str | None = None
    verificado_em: datetime
    tempo_resposta_ms: int | None = None
    origem: str
    resposta_bruta: str | None = None
    criado_em: datetime
