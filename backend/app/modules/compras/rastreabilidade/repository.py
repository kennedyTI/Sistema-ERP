"""Repository das consultas Protheus usando a integracao bdTotvs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from backend.app.modules.integracoes import bdTotvs


SQL_DIR = Path(__file__).resolve().parent / "sql"


def read_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text(encoding="utf-8")


def values_placeholder(row_count: int, column_count: int) -> str:
    return ",\n        ".join(
        ["(" + ", ".join(["?"] * column_count) + ")"] * row_count
    )


def dedup_tuples(rows: Iterable[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    seen = set()
    result: list[tuple[Any, ...]] = []
    for row in rows:
        normalized = tuple("" if value is None else str(value).strip() for value in row)
        if not all(normalized) or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


class ComprasRastreabilidadeRepository:
    def fetch_base_sc_pedido(self) -> list[dict[str, Any]]:
        return bdTotvs.execute_query(read_sql("01_base_sc_pedido.sql"))

    def _fetch_with_values(
        self,
        filename: str,
        rows: list[tuple[Any, ...]],
    ) -> list[dict[str, Any]]:
        if not rows:
            return []
        column_count = len(rows[0])
        sql = read_sql(filename).format(
            values=values_placeholder(len(rows), column_count)
        )
        params = tuple(value for row in rows for value in row)
        return bdTotvs.execute_query(sql, params=params)

    def fetch_entradas_sd1(
        self,
        chaves_pedido: list[tuple[Any, ...]],
    ) -> list[dict[str, Any]]:
        return self._fetch_with_values("02_entradas_sd1.sql", chaves_pedido)

    def fetch_fiscal_sf1(self, nfs: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return self._fetch_with_values("03_fiscal_sf1.sql", nfs)

    def fetch_financeiro_se2(self, nfs: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
        return self._fetch_with_values("04_financeiro_se2.sql", nfs)

    def fetch_produtos_sb1(
        self,
        produtos: list[tuple[Any, ...]],
    ) -> list[dict[str, Any]]:
        return self._fetch_with_values("05_produtos_sb1.sql", produtos)

    def fetch_estoque_sb2(
        self,
        chaves_estoque: list[tuple[Any, ...]],
    ) -> list[dict[str, Any]]:
        return self._fetch_with_values("06_estoque_sb2.sql", chaves_estoque)

    def fetch_locais_nnr(
        self,
        locais: list[tuple[Any, ...]],
    ) -> list[dict[str, Any]]:
        return self._fetch_with_values("07_locais_nnr.sql", locais)
