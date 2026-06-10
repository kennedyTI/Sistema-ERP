"""Contratos em portugues da API de maquinas do modulo Impressoras."""

from datetime import datetime
from ipaddress import ip_address
from typing import Generic, TypeVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")


class RespostaMaquinas(BaseModel, Generic[T]):
    sucesso: bool
    mensagem: str | None = None
    dados: T | None = None
    erros: dict[str, list[str]] | None = None


class ModeloImpressoraRead(BaseModel):
    id: int
    fabricante: str
    modelo: str
    tipo: str | None = None
    cor_modelo: str | None = None
    url_imagem: str | None = None


class MaquinaRead(BaseModel):
    id: int
    nome: str
    endereco_ip: str
    modelo_id: int | None = None
    fabricante: str | None = None
    modelo: str | None = None
    tipo: str | None = None
    cor_modelo: str | None = None
    setor: str | None = None
    centro_custo: str | None = None
    ativo: bool
    observacoes: str | None = None
    url_imagem: str | None = None
    criado_em: datetime
    atualizado_em: datetime


class MaquinaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nome: str = Field(
        min_length=1,
        max_length=160,
        validation_alias=AliasChoices("nome", "name"),
    )
    endereco_ip: str = Field(
        min_length=1,
        max_length=45,
        validation_alias=AliasChoices("endereco_ip", "ip_address"),
    )
    modelo_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("modelo_id", "model_id"),
    )
    fabricante: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("fabricante", "manufacturer"),
    )
    modelo: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("modelo", "model"),
    )
    tipo: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("tipo", "type"),
    )
    cor_modelo: str | None = Field(
        default=None,
        max_length=40,
        validation_alias=AliasChoices("cor_modelo", "color_mode"),
    )
    setor: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("setor", "sector"),
    )
    centro_custo: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("centro_custo", "cost_center"),
    )
    ativo: bool = Field(
        default=True,
        validation_alias=AliasChoices("ativo", "is_active"),
    )
    observacoes: str | None = Field(
        default=None,
        validation_alias=AliasChoices("observacoes", "notes"),
    )

    @field_validator(
        "nome",
        "endereco_ip",
        "fabricante",
        "modelo",
        "tipo",
        "cor_modelo",
        "setor",
        "centro_custo",
        "observacoes",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("endereco_ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        try:
            ip_address(value)
        except ValueError as exc:
            raise ValueError("Informe um endereco IP valido.") from exc
        return value

    @model_validator(mode="after")
    def validate_model(self):
        has_legacy_model = bool(self.fabricante and self.modelo)
        if self.modelo_id is None and not has_legacy_model:
            raise ValueError("Informe um modelo de impressora.")
        if bool(self.fabricante) != bool(self.modelo):
            raise ValueError("Fabricante e modelo devem ser informados juntos.")
        return self


class MaquinaUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    nome: str | None = Field(
        default=None,
        min_length=1,
        max_length=160,
        validation_alias=AliasChoices("nome", "name"),
    )
    endereco_ip: str | None = Field(
        default=None,
        min_length=1,
        max_length=45,
        validation_alias=AliasChoices("endereco_ip", "ip_address"),
    )
    modelo_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("modelo_id", "model_id"),
    )
    setor: str | None = Field(
        default=None,
        max_length=120,
        validation_alias=AliasChoices("setor", "sector"),
    )
    centro_custo: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("centro_custo", "cost_center"),
    )
    observacoes: str | None = Field(
        default=None,
        validation_alias=AliasChoices("observacoes", "notes"),
    )
    atualizado_em: datetime = Field(
        validation_alias=AliasChoices("atualizado_em", "updated_at"),
    )

    @field_validator(
        "nome",
        "endereco_ip",
        "setor",
        "centro_custo",
        "observacoes",
        mode="before",
    )
    @classmethod
    def normalize_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("endereco_ip")
    @classmethod
    def validate_ip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ip_address(value)
        except ValueError as exc:
            raise ValueError("Informe um endereco IP valido.") from exc
        return value


class MaquinaStatusUpdate(BaseModel):
    ativo: bool = Field(validation_alias=AliasChoices("ativo", "is_active"))


class ResumoMaquinas(BaseModel):
    total_maquinas: int
    ativas: int
    inativas: int
    fabricantes: int
    modelos_cadastrados: int


class StatusOperacionalResumo(BaseModel):
    status: str
    alerta: str | None = None
    mensagem: str | None = None
    ultima_verificacao_em: datetime | None = None


class LogOperacionalRead(BaseModel):
    id: int
    tipo_evento: str
    status_anterior: str | None = None
    status_novo: str | None = None
    alerta_anterior: str | None = None
    alerta_novo: str | None = None
    mensagem: str | None = None
    verificado_em: datetime
    origem: str


class AcoesMaquina(BaseModel):
    pode_editar: bool
    pode_alternar_status: bool


class DetalhesMaquina(BaseModel):
    maquina: MaquinaRead
    modelo_dados: ModeloImpressoraRead | None = None
    status_operacional: StatusOperacionalResumo | None = None
    logs_recentes: list[LogOperacionalRead] = Field(default_factory=list)
    acoes: AcoesMaquina


class ResultadoToggleMaquina(BaseModel):
    maquina: MaquinaRead
    resumo: ResumoMaquinas


class ResultadoMaquina(BaseModel):
    maquina: MaquinaRead
