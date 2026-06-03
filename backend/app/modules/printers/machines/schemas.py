"""Schemas de leitura de maquinas."""

from pydantic import BaseModel, ConfigDict


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str | None = None
