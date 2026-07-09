"""Schemas publicos do catalogo de suprimentos."""

from pydantic import BaseModel, ConfigDict


class PrinterSupplyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    suprimento: str
    cor: str | None = None
    codigo_protheus: str | None = None
