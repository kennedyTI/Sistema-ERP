"""Seed idempotente das configuracoes SNMP/OIDs iniciais."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.modules.printers.machines.models import PrinterModel
from backend.app.modules.printers.status.models import (  # noqa: F401
    HistoricoStatusImpressora,
    LogImpressora,
    StatusImpressora,
)
from backend.app.modules.printers.monitoring.snmp.models import (
    ALLOWED_METRIC_KEYS,
    ALLOWED_QUERY_MODES,
    ALLOWED_SNMP_VERSIONS,
    ALLOWED_VALUE_TYPES,
    PrinterSnmpOid,
)


PRT_ALERT_DESCRIPTION_BASE_OID = "1.3.6.1.2.1.43.18.1.1.8"

INITIAL_SNMP_OIDS = (
    {
        "fabricante": "Brother",
        "modelo": "DCP-L1632W",
        "versao_snmp": "2c",
        "metricas": {
            "alert_raw": ("1.3.6.1.2.1.43.18.1.1.8.1.1", "string", "get"),
            "name": ("1.3.6.1.2.1.1.5.0", "string", "get"),
            "location": ("1.3.6.1.2.1.1.6.0", "string", "get"),
            "page_count_total": (
                "1.3.6.1.2.1.43.10.2.1.4.1.1",
                "counter",
                "get",
            ),
        },
    },
    {
        "fabricante": "Brother",
        "modelo": "DCP-L2540DW",
        "versao_snmp": "2c",
        "metricas": {
            "alert_raw": (PRT_ALERT_DESCRIPTION_BASE_OID, "string", "walk"),
            "name": ("1.3.6.1.2.1.1.5.0", "string", "get"),
            "location": ("1.3.6.1.2.1.1.6.0", "string", "get"),
            "page_count_total": (
                "1.3.6.1.2.1.43.10.2.1.4.1.1",
                "counter",
                "get",
            ),
        },
    },
    {
        "fabricante": "Canon",
        "modelo": "IR-C3326I",
        "versao_snmp": "1",
        "metricas": {
            "alert_raw": (PRT_ALERT_DESCRIPTION_BASE_OID, "string", "walk"),
            "name": ("1.3.6.1.2.1.1.5.0", "string", "get"),
            "location": ("1.3.6.1.2.1.1.6.0", "string", "get"),
            "page_count_total": (
                "1.3.6.1.2.1.43.10.2.1.4.1.1",
                "counter",
                "get",
            ),
        },
    },
    {
        "fabricante": "HP",
        "modelo": "MFP-4303",
        "versao_snmp": "2c",
        "metricas": {
            "alert_raw": ("1.3.6.1.2.1.25.3.5.1.1.1", "string", "get"),
            "name": ("1.3.6.1.2.1.1.5.0", "string", "get"),
            "location": ("1.3.6.1.2.1.1.6.0", "string", "get"),
            "page_count_total": (
                "1.3.6.1.2.1.43.10.2.1.4.1.1",
                "counter",
                "get",
            ),
        },
    },
    {
        "fabricante": "Samsung",
        "modelo": "K-4350",
        "versao_snmp": "2c",
        "metricas": {
            "alert_raw": ("1.3.6.1.2.1.25.3.5.1.1.1", "string", "get"),
            "name": ("1.3.6.1.2.1.1.5.0", "string", "get"),
            "location": ("1.3.6.1.2.1.1.6.0", "string", "get"),
            "page_count_total": (
                "1.3.6.1.2.1.43.10.2.1.4.1.1",
                "counter",
                "get",
            ),
        },
    },
)

INVALIDATED_SNMP_OIDS = (
    {
        "fabricante": "Brother",
        "modelo": "DCP-L1632W",
        "chave_metrica": "toner_black",
        "oid": "1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.52.31.1.2.1",
        "motivo": "Falso 100% em impressora com status.html indicando substituir toner.",
    },
    {
        "fabricante": "Brother",
        "modelo": "DCP-L2540DW",
        "chave_metrica": "toner_black",
        "oid": "1.3.6.1.4.1.2435.2.3.9.4.2.1.3.3.1.11.0",
        "motivo": "OID privado Brother mantido fora do seed ate nova validacao.",
    },
)


@dataclass(frozen=True)
class PrinterSnmpOidSeedResult:
    created: int
    updated: int
    unchanged: int
    ignored: int
    total: int
    ignored_models: tuple[str, ...] = field(default_factory=tuple)


def normalize_lookup(value: str | None) -> str:
    """Remove acentos e padroniza texto para localizar modelos."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().strip().split())


def iter_seed_entries(items: Iterable[dict] = INITIAL_SNMP_OIDS) -> list[dict]:
    """Expande o seed por modelo em linhas modelo + metrica."""
    entries: list[dict] = []
    for item in items:
        fabricante = str(item["fabricante"]).strip()
        modelo = str(item["modelo"]).strip()
        versao_snmp = str(item.get("versao_snmp") or "2c").strip()

        for chave_metrica, metric_data in item["metricas"].items():
            oid, tipo_valor, *modo_consulta_data = metric_data
            modo_consulta = modo_consulta_data[0] if modo_consulta_data else "get"
            entries.append(
                {
                    "fabricante": fabricante,
                    "modelo": modelo,
                    "chave_metrica": str(chave_metrica).strip(),
                    "oid": str(oid).strip(),
                    "tipo_valor": str(tipo_valor).strip(),
                    "versao_snmp": versao_snmp,
                    "modo_consulta": str(modo_consulta).strip(),
                    "ativo": True,
                }
            )
    return entries


def _validate_entry(entry: dict) -> None:
    if entry["chave_metrica"] not in ALLOWED_METRIC_KEYS:
        raise ValueError(f"chave_metrica invalida: {entry['chave_metrica']}")
    if entry["tipo_valor"] not in ALLOWED_VALUE_TYPES:
        raise ValueError(f"tipo_valor invalido: {entry['tipo_valor']}")
    if entry["versao_snmp"] not in ALLOWED_SNMP_VERSIONS:
        raise ValueError(f"versao_snmp invalida: {entry['versao_snmp']}")
    if entry["modo_consulta"] not in ALLOWED_QUERY_MODES:
        raise ValueError(f"modo_consulta invalido: {entry['modo_consulta']}")
    if not entry["oid"]:
        raise ValueError("oid ausente")


def _load_models(db: Session) -> list[SimpleNamespace]:
    rows = db.execute(
        select(
            PrinterModel.__table__.c.id,
            PrinterModel.__table__.c.manufacturer,
            PrinterModel.__table__.c.name,
        )
    ).all()
    return [
        SimpleNamespace(id=row.id, manufacturer=row.manufacturer, name=row.name)
        for row in rows
    ]


def _find_model(
    models: list[SimpleNamespace],
    *,
    manufacturer: str,
    model_name: str,
) -> PrinterModel | None:
    manufacturer_key = normalize_lookup(manufacturer)
    model_key = normalize_lookup(model_name)
    for model in models:
        if (
            normalize_lookup(model.manufacturer) == manufacturer_key
            and normalize_lookup(model.name) == model_key
        ):
            return model

    matches_by_name = [
        model for model in models if normalize_lookup(model.name) == model_key
    ]
    if len(matches_by_name) == 1:
        return matches_by_name[0]
    return None


def seed_printer_snmp_oids(
    db: Session,
    entries: Iterable[dict] | None = None,
) -> PrinterSnmpOidSeedResult:
    """Sincroniza OIDs oficiais sem duplicar modelo + metrica."""
    seed_entries = list(entries) if entries is not None else iter_seed_entries()
    models = _load_models(db)
    created = 0
    updated = 0
    unchanged = 0
    ignored = 0
    ignored_models: list[str] = []

    for entry in seed_entries:
        _validate_entry(entry)
        model = _find_model(
            models,
            manufacturer=entry["fabricante"],
            model_name=entry["modelo"],
        )
        if model is None:
            ignored += 1
            ignored_models.append(f"{entry['fabricante']} {entry['modelo']}")
            continue

        current = (
            db.query(PrinterSnmpOid)
            .filter(
                PrinterSnmpOid.modelo_id == model.id,
                PrinterSnmpOid.chave_metrica == entry["chave_metrica"],
            )
            .one_or_none()
        )
        controlled = {
            "oid": entry["oid"],
            "tipo_valor": entry["tipo_valor"],
            "versao_snmp": entry["versao_snmp"],
            "modo_consulta": entry["modo_consulta"],
            "ativo": bool(entry.get("ativo", True)),
        }

        if current is None:
            db.add(
                PrinterSnmpOid(
                    modelo_id=model.id,
                    chave_metrica=entry["chave_metrica"],
                    **controlled,
                )
            )
            created += 1
            continue

        changed = any(getattr(current, key) != value for key, value in controlled.items())
        if not changed:
            unchanged += 1
            continue

        for key, value in controlled.items():
            setattr(current, key, value)
        updated += 1

    db.commit()
    return PrinterSnmpOidSeedResult(
        created=created,
        updated=updated,
        unchanged=unchanged,
        ignored=ignored,
        total=len(seed_entries),
        ignored_models=tuple(sorted(set(ignored_models))),
    )
