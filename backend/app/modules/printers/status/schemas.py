"""Schemas da API de status operacional das impressoras."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


StatusOperacional = Literal["online", "offline"]
NivelAlerta = Literal["cinza", "verde", "amarelo", "vermelho"]
SeveridadeStatus = Literal["unknown", "green", "low", "medium", "high"]
OrigemStatus = Literal["sistema", "manual", "seed", "futuro_snmp"]
MetodoConfirmacao = Literal["icmp", "tcp", "snmp", "html", "fallback"]


class PrinterStatusAlertRead(BaseModel):
    codigo: str
    mensagem: str
    nivel_alerta: NivelAlerta
    severidade: SeveridadeStatus
    prioridade: int


class PrinterTonerRead(BaseModel):
    cor: Literal["black", "cyan", "magenta", "yellow", "unknown"]
    nome: str
    percentual: int | None = None
    descricao: str | None = None
    origem_coleta: Literal["snmp"]
    metodo_coleta: Literal["printer_mib_walk"]
    coletado_em: datetime | None = None


class PrinterStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    machine_id: int
    id: int
    machine_name: str
    maquina: str
    ip_address: str
    ip: str
    manufacturer: str | None = None
    fabricante: str | None = None
    model: str | None = None
    modelo: str | None = None
    modelo_exibicao: str | None = None
    url_imagem: str | None = None
    sector: str | None = None
    local: str | None = None
    cost_center: str | None = None
    status_operacional: StatusOperacional
    status: StatusOperacional
    nivel_alerta: NivelAlerta
    severidade: SeveridadeStatus
    alerta: str | None = None
    alertas: list[PrinterStatusAlertRead] = Field(default_factory=list)
    toners: list[PrinterTonerRead] = Field(default_factory=list)
    mensagem: str | None = None
    mensagem_alerta: str | None = None
    mensagem_operador: str
    ultima_verificacao_em: datetime | None = None
    verificado_em: datetime | None = None
    ultimo_sucesso_em: datetime | None = None
    ultima_falha_em: datetime | None = None
    tempo_resposta_ms: int | None = None
    metodo_confirmacao: MetodoConfirmacao | None = None
    origem: OrigemStatus


class PrinterStatusSummary(BaseModel):
    total_impressoras: int
    online: int
    offline: int
    com_alerta: int
    substituir_toner: int


class PrinterLogRead(BaseModel):
    id: str
    data_hora: datetime
    tipo: str
    mensagem: str
    origem: Literal["status", "alerta"]
