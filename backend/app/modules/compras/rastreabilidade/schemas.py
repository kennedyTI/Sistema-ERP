"""Schemas internos do backend de rastreabilidade de compras."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RastreabilidadeContagens:
    base_sc_pedido: int = 0
    entradas_sd1: int = 0
    fiscal_sf1: int = 0
    financeiro_se2: int = 0
    produtos_sb1: int = 0
    estoque_sb2: int = 0
    locais_nnr: int = 0
    itens_snapshot: int = 0


@dataclass(frozen=True)
class RastreabilidadeResultado:
    itens: list[dict[str, Any]]
    contagens: RastreabilidadeContagens = field(default_factory=RastreabilidadeContagens)
