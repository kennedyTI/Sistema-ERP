"""Schemas do cadastro de maquinas."""

from datetime import datetime
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ip_address: str
    manufacturer: str | None = None
    model: str | None = None
    sector: str | None = None
    cost_center: str | None = None
    is_active: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    ip_address: str = Field(min_length=1, max_length=45)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    sector: str | None = Field(default=None, max_length=120)
    cost_center: str | None = Field(default=None, max_length=80)
    is_active: bool = True
    notes: str | None = None

    @field_validator("name", "ip_address", "manufacturer", "model", "sector", "cost_center", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str | None) -> str:
        if not value:
            raise ValueError("Nome da maquina e obrigatorio.")
        return value

    @field_validator("ip_address")
    @classmethod
    def valid_ip_address(cls, value: str | None) -> str:
        if not value:
            raise ValueError("IP da maquina e obrigatorio.")
        try:
            ip_address(value)
        except ValueError as exc:
            raise ValueError("IP da maquina deve ser valido.") from exc
        return value


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    ip_address: str | None = Field(default=None, min_length=1, max_length=45)
    manufacturer: str | None = Field(default=None, max_length=120)
    model: str | None = Field(default=None, max_length=120)
    sector: str | None = Field(default=None, max_length=120)
    cost_center: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None
    notes: str | None = None

    @field_validator("name", "ip_address", "manufacturer", "model", "sector", "cost_center", mode="before")
    @classmethod
    def normalize_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    @field_validator("ip_address")
    @classmethod
    def valid_ip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ip_address(value)
        except ValueError as exc:
            raise ValueError("IP da maquina deve ser valido.") from exc
        return value


class MachineStatusUpdate(BaseModel):
    is_active: bool
