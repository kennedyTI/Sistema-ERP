"""Modelo de dominio inicial para maquinas, ainda sem persistencia."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PrinterMachine:
    id: int
    name: str
    location: str | None = None
