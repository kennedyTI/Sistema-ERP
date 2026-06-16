"""Diagnostico manual SNMP dos alertas brutos de impressoras.

Uso seguro:

    python backend/pyteste/diagnostico_snmp_alertas.py
    python backend/pyteste/diagnostico_snmp_alertas.py --confirmar
    python backend/pyteste/diagnostico_snmp_alertas.py --confirmar --modelo "Brother DCP-L1632W"
    python backend/pyteste/diagnostico_snmp_alertas.py --confirmar --maquina-id 12

Sem ``--confirmar`` o script faz apenas dry-run: lista o que seria coletado e
nao consulta impressoras reais.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable

from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    getCmd,
    nextCmd,
)
from sqlalchemy import and_, select
from sqlalchemy.orm import Session


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.database import SessionLocal  # noqa: E402
from backend.app.modules.printers.machines.models import (  # noqa: E402
    PrinterMachine,
    PrinterModel,
)
from backend.app.modules.printers.monitoring.config import (  # noqa: E402
    MonitoringSettings,
    get_monitoring_settings,
)
from backend.app.modules.printers.monitoring.probes import detect_connectivity  # noqa: E402
from backend.app.modules.printers.monitoring.snmp.models import PrinterSnmpOid  # noqa: E402
from backend.app.modules.printers.status.models import StatusImpressora  # noqa: E402


OUTPUT_DIR = Path("tmp/diagnosticos/snmp_alertas")
MAX_OIDS_PER_WALK = 50
WALK_BASES = (
    {
        "nome": "prtAlertDescription",
        "base_oid": "1.3.6.1.2.1.43.18.1.1.8",
    },
    {
        "nome": "hrPrinterStatus",
        "base_oid": "1.3.6.1.2.1.25.3.5.1.1",
    },
    {
        "nome": "hrPrinterDetectedErrorState",
        "base_oid": "1.3.6.1.2.1.25.3.5.1.2",
    },
)


@dataclass(frozen=True)
class DiagnosticTarget:
    modelo_id: int
    fabricante: str
    modelo: str
    oid_alert_raw: str
    tipo_valor: str
    versao_snmp: str
    maquina_id: int | None
    maquina: str | None
    ip: str | None
    status_previo: str | None = None
    motivo_ignorado: str | None = None


def normalize_lookup(value: str | None) -> str:
    """Normaliza texto apenas para filtros e comparacoes internas."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().strip().split())


def normalize_for_display(value: Any) -> str | None:
    """Gera uma versao curta de exibicao sem substituir o valor bruto."""
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    return " ".join(text.split()) or None


def _latency_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def emitir(texto: str = "") -> None:
    sys.stdout.write(f"{texto}\n")


def _snmp_mp_model(snmp_version: str | None) -> int:
    return 0 if str(snmp_version or "").strip() == "1" else 1


def _sanitize_error(error: Any, community: str | None = None) -> str | None:
    if error is None:
        return None
    text = str(error)
    if community:
        text = text.replace(community, "[community_oculta]")
    return text[:500]


def serialize_snmp_value(value: Any) -> dict[str, Any]:
    """Preserva a forma bruta do valor retornado pelo SNMP."""
    value_str = value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)
    payload: dict[str, Any] = {
        "tipo_snmp": type(value).__name__,
        "valor_str": value_str,
        "valor_repr": repr(value),
        "valor_texto_normalizado_apenas_para_exibicao": normalize_for_display(value_str),
        "tamanho": len(str(value_str)),
    }

    raw_bytes: bytes | None = None
    if hasattr(value, "asOctets"):
        try:
            raw_bytes = bytes(value.asOctets())
        except Exception:
            raw_bytes = None
    elif isinstance(value, bytes):
        raw_bytes = value

    if raw_bytes is not None:
        payload["valor_bytes_hex"] = raw_bytes.hex()
        payload["tamanho"] = len(raw_bytes)
        try:
            payload["decodificacao_utf8"] = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            payload["decodificacao_utf8"] = None
        payload["decodificacao_latin1"] = raw_bytes.decode("latin1", errors="replace")

    return payload


def build_get_result(
    *,
    oid: str,
    value: Any | None = None,
    success: bool = True,
    latency_ms: int | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    community: str | None = None,
) -> dict[str, Any]:
    value_payload = serialize_snmp_value(value) if success and value is not None else None
    return {
        "operacao": "get",
        "chave_metrica": "alert_raw",
        "oid": oid,
        "sucesso": bool(success and value is not None),
        "quantidade_valores": 1 if success and value is not None else 0,
        "valor_bruto": value_payload,
        "tipo_valor_snmp": value_payload["tipo_snmp"] if value_payload else None,
        "representacao_python": value_payload["valor_repr"] if value_payload else None,
        "valor_texto_normalizado_apenas_para_exibicao": (
            value_payload["valor_texto_normalizado_apenas_para_exibicao"]
            if value_payload
            else None
        ),
        "latencia_ms": latency_ms,
        "erro_codigo": error_code,
        "erro_detalhe_sanitizado": _sanitize_error(error_detail, community),
    }


def build_walk_result(
    *,
    base_oid: str,
    nome: str,
    values: Iterable[tuple[str, Any]] = (),
    success: bool = True,
    latency_ms: int | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    community: str | None = None,
) -> dict[str, Any]:
    serialized_values = [
        {
            "oid_retornado": returned_oid,
            **serialize_snmp_value(value),
        }
        for returned_oid, value in values
    ]
    return {
        "operacao": "walk",
        "nome": nome,
        "base_oid": base_oid,
        "sucesso": bool(success),
        "quantidade_retornada": len(serialized_values),
        "valores": serialized_values,
        "latencia_ms": latency_ms,
        "erro_codigo": error_code,
        "erro_detalhe_sanitizado": _sanitize_error(error_detail, community),
    }


def snmp_get_raw(
    *,
    host: str,
    oid: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    if not community:
        return build_get_result(
            oid=oid,
            success=False,
            error_code="community_nao_configurada",
            error_detail="PRINTER_SNMP_COMMUNITY nao configurada.",
        )

    started_at = perf_counter()
    try:
        response = next(
            getCmd(
                SnmpEngine(),
                CommunityData(community, mpModel=_snmp_mp_model(snmp_version)),
                UdpTransportTarget((host, 161), timeout=timeout_seconds, retries=0),
                ContextData(),
                ObjectType(ObjectIdentity(oid)),
            )
        )
        error_indication, error_status, _, var_binds = response
    except Exception as exc:
        return build_get_result(
            oid=oid,
            success=False,
            latency_ms=_latency_ms(started_at),
            error_code="excecao_snmp",
            error_detail=str(exc),
            community=community,
        )

    if error_indication or error_status or not var_binds:
        return build_get_result(
            oid=oid,
            success=False,
            latency_ms=_latency_ms(started_at),
            error_code="erro_snmp",
            error_detail=error_indication or error_status or "sem_varbind",
            community=community,
        )

    return build_get_result(
        oid=oid,
        value=var_binds[0][1],
        latency_ms=_latency_ms(started_at),
        community=community,
    )


def snmp_walk_raw(
    *,
    host: str,
    base_oid: str,
    nome: str,
    community: str,
    snmp_version: str,
    timeout_seconds: float,
    max_oids: int = MAX_OIDS_PER_WALK,
) -> dict[str, Any]:
    if not community:
        return build_walk_result(
            base_oid=base_oid,
            nome=nome,
            success=False,
            error_code="community_nao_configurada",
            error_detail="PRINTER_SNMP_COMMUNITY nao configurada.",
        )

    started_at = perf_counter()
    values: list[tuple[str, Any]] = []
    try:
        iterator = nextCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=_snmp_mp_model(snmp_version)),
            UdpTransportTarget((host, 161), timeout=timeout_seconds, retries=0),
            ContextData(),
            ObjectType(ObjectIdentity(base_oid)),
            lexicographicMode=False,
        )
        for error_indication, error_status, _, var_binds in iterator:
            if error_indication or error_status:
                return build_walk_result(
                    base_oid=base_oid,
                    nome=nome,
                    values=values,
                    success=False,
                    latency_ms=_latency_ms(started_at),
                    error_code="erro_snmp",
                    error_detail=error_indication or error_status,
                    community=community,
                )
            for oid_obj, value in var_binds:
                values.append((str(oid_obj), value))
                if len(values) >= max_oids:
                    return build_walk_result(
                        base_oid=base_oid,
                        nome=nome,
                        values=values,
                        latency_ms=_latency_ms(started_at),
                        community=community,
                    )
    except Exception as exc:
        return build_walk_result(
            base_oid=base_oid,
            nome=nome,
            values=values,
            success=False,
            latency_ms=_latency_ms(started_at),
            error_code="excecao_snmp",
            error_detail=str(exc),
            community=community,
        )

    return build_walk_result(
        base_oid=base_oid,
        nome=nome,
        values=values,
        latency_ms=_latency_ms(started_at),
        community=community,
    )


def load_candidate_rows(
    db: Session,
    *,
    modelo_filter: str | None = None,
    maquina_id: int | None = None,
) -> list[dict[str, Any]]:
    models = PrinterModel.__table__
    machines = PrinterMachine.__table__
    oids = PrinterSnmpOid.__table__
    statuses = StatusImpressora.__table__
    query = (
        select(
            models.c.id.label("modelo_id"),
            models.c.manufacturer.label("fabricante"),
            models.c.name.label("modelo"),
            oids.c.oid.label("oid_alert_raw"),
            oids.c.tipo_valor,
            oids.c.versao_snmp,
            machines.c.id.label("maquina_id"),
            machines.c.name.label("maquina"),
            machines.c.ip_address.label("ip"),
            machines.c.is_active.label("maquina_ativa"),
            statuses.c.status_operacional.label("status_previo"),
        )
        .select_from(
            models.join(
                oids,
                and_(
                    oids.c.modelo_id == models.c.id,
                    oids.c.chave_metrica == "alert_raw",
                    oids.c.ativo.is_(True),
                ),
            )
            .outerjoin(
                machines,
                and_(
                    machines.c.model_id == models.c.id,
                    machines.c.is_active.is_(True),
                ),
            )
            .outerjoin(statuses, statuses.c.maquina_id == machines.c.id)
        )
        .order_by(models.c.manufacturer.asc(), models.c.name.asc(), machines.c.id.asc())
    )
    if maquina_id is not None:
        query = query.where(machines.c.id == maquina_id)

    rows = [dict(row._mapping) for row in db.execute(query).all()]
    if modelo_filter:
        needle = normalize_lookup(modelo_filter)
        rows = [
            row
            for row in rows
            if needle in normalize_lookup(f"{row['fabricante']} {row['modelo']}")
        ]
    return rows


def select_diagnostic_targets(
    candidates: Iterable[dict[str, Any]],
    *,
    testar_todas: bool = False,
) -> list[DiagnosticTarget]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in candidates:
        grouped.setdefault(int(row["modelo_id"]), []).append(row)

    targets: list[DiagnosticTarget] = []
    for model_id in sorted(grouped):
        rows = grouped[model_id]
        first = rows[0]
        active_rows = [
            row
            for row in rows
            if row.get("maquina_id") is not None and row.get("maquina_ativa") is not False
        ]
        active_rows.sort(key=lambda row: int(row["maquina_id"]))
        selected_rows = active_rows if testar_todas else active_rows[:1]
        if not selected_rows:
            targets.append(
                DiagnosticTarget(
                    modelo_id=model_id,
                    fabricante=first["fabricante"],
                    modelo=first["modelo"],
                    oid_alert_raw=first["oid_alert_raw"],
                    tipo_valor=first["tipo_valor"],
                    versao_snmp=first["versao_snmp"],
                    maquina_id=None,
                    maquina=None,
                    ip=None,
                    status_previo=None,
                    motivo_ignorado="sem_maquina_ativa",
                )
            )
            continue
        for row in selected_rows:
            targets.append(
                DiagnosticTarget(
                    modelo_id=model_id,
                    fabricante=row["fabricante"],
                    modelo=row["modelo"],
                    oid_alert_raw=row["oid_alert_raw"],
                    tipo_valor=row["tipo_valor"],
                    versao_snmp=row["versao_snmp"],
                    maquina_id=row["maquina_id"],
                    maquina=row["maquina"],
                    ip=row["ip"],
                    status_previo=row.get("status_previo"),
                )
            )
    return targets


def check_online_with_connectivity(
    target: DiagnosticTarget,
    settings: MonitoringSettings,
) -> dict[str, Any]:
    if not target.ip:
        return {"online": False, "metodo": None, "motivo": "sem_ip"}
    detection = detect_connectivity(target.ip, settings)
    return {
        "online": detection.online,
        "metodo": detection.method,
        "latencia_ms": detection.latency_ms,
        "tentativas": detection.attempts,
    }


def useful_count(values: list[dict[str, Any]]) -> int:
    return sum(
        1
        for value in values
        if normalize_for_display(value.get("valor_str")) not in {None, ""}
    )


def preliminary_conclusion(get_result: dict[str, Any] | None, walks: list[dict[str, Any]]) -> str:
    if get_result is None:
        return "Modelo sem maquina online"

    prt_walk = next(
        (walk for walk in walks if walk.get("nome") == "prtAlertDescription"),
        None,
    )
    get_ok = bool(get_result.get("sucesso") and get_result.get("quantidade_valores") == 1)
    walk_useful = useful_count(prt_walk.get("valores", [])) if prt_walk else 0

    if get_ok and walk_useful <= 1:
        return "GET suficiente"
    if get_ok and walk_useful > 1:
        return "WALK necessario para multiplos alertas"
    if not get_ok and walk_useful > 0:
        return "WALK pode ser necessario"
    return "SNMP nao respondeu ou OID invalido"


def sanitize_sensitive_data(data: Any, community: str | None) -> Any:
    if isinstance(data, dict):
        return {
            key: sanitize_sensitive_data(value, community)
            for key, value in data.items()
            if key not in {"community", "snmp_community"}
        }
    if isinstance(data, list):
        return [sanitize_sensitive_data(item, community) for item in data]
    if isinstance(data, str) and community:
        return data.replace(community, "[community_oculta]")
    return data


def diagnose_target(
    target: DiagnosticTarget,
    *,
    settings: MonitoringSettings,
    connectivity_checker: Callable[[DiagnosticTarget, MonitoringSettings], dict[str, Any]],
    snmp_get: Callable[..., dict[str, Any]],
    snmp_walk: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "modelo_id": target.modelo_id,
        "fabricante": target.fabricante,
        "modelo": target.modelo,
        "maquina_id": target.maquina_id,
        "maquina": target.maquina,
        "ip": target.ip,
        "status_previo": target.status_previo,
        "oid_alert_raw": target.oid_alert_raw,
        "versao_snmp": target.versao_snmp,
    }
    if target.motivo_ignorado:
        return {
            **base,
            "online_antes_da_coleta": False,
            "resultado_verificacao_online": None,
            "motivo_ignorado": target.motivo_ignorado,
            "get_alert_raw": None,
            "walks": [],
            "conclusao_preliminar": "Modelo sem maquina online",
        }

    online_result = connectivity_checker(target, settings)
    if not online_result.get("online"):
        return {
            **base,
            "online_antes_da_coleta": False,
            "resultado_verificacao_online": online_result,
            "motivo_ignorado": "maquina_offline",
            "get_alert_raw": None,
            "walks": [],
            "conclusao_preliminar": "Modelo sem maquina online",
        }

    get_result = snmp_get(
        host=target.ip,
        oid=target.oid_alert_raw,
        community=settings.snmp_community,
        snmp_version=target.versao_snmp,
        timeout_seconds=settings.snmp_timeout_seconds,
    )
    walks = [
        snmp_walk(
            host=target.ip,
            base_oid=base_config["base_oid"],
            nome=base_config["nome"],
            community=settings.snmp_community,
            snmp_version=target.versao_snmp,
            timeout_seconds=settings.snmp_timeout_seconds,
            max_oids=MAX_OIDS_PER_WALK,
        )
        for base_config in WALK_BASES
    ]
    return {
        **base,
        "online_antes_da_coleta": True,
        "resultado_verificacao_online": online_result,
        "motivo_ignorado": None,
        "get_alert_raw": get_result,
        "walks": walks,
        "conclusao_preliminar": preliminary_conclusion(get_result, walks),
    }


def build_report(
    *,
    targets: list[DiagnosticTarget],
    confirmar: bool,
    settings: MonitoringSettings,
    connectivity_checker: Callable[[DiagnosticTarget, MonitoringSettings], dict[str, Any]] = check_online_with_connectivity,
    snmp_get: Callable[..., dict[str, Any]] = snmp_get_raw,
    snmp_walk: Callable[..., dict[str, Any]] = snmp_walk_raw,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    generated_at = timestamp or datetime.now()
    if not confirmar:
        return sanitize_sensitive_data(
            {
                "executado": False,
                "modo": "dry_run",
                "gerado_em": generated_at.isoformat(timespec="seconds"),
                "mensagem": "Use --confirmar para consultar impressoras reais.",
                "alvos_planejados": [target.__dict__ for target in targets],
            },
            settings.snmp_community,
        )

    results = [
        diagnose_target(
            target,
            settings=settings,
            connectivity_checker=connectivity_checker,
            snmp_get=snmp_get,
            snmp_walk=snmp_walk,
        )
        for target in targets
    ]
    return sanitize_sensitive_data(
        {
            "executado": True,
            "modo": "confirmado",
            "gerado_em": generated_at.isoformat(timespec="seconds"),
            "walk_bases": WALK_BASES,
            "max_oids_por_walk": MAX_OIDS_PER_WALK,
            "resultados": results,
        },
        settings.snmp_community,
    )


def _count_walk(result: dict[str, Any], name: str) -> int:
    for walk in result.get("walks") or []:
        if walk.get("nome") == name:
            return int(walk.get("quantidade_retornada") or 0)
    return 0


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Diagnostico SNMP de alertas",
        "",
        f"- Gerado em: {report.get('gerado_em')}",
        f"- Modo: {report.get('modo')}",
        "",
    ]
    if not report.get("executado"):
        lines.extend(
            [
                "## Dry-run",
                "",
                "Nenhuma impressora real foi consultada. Use `--confirmar` para executar GET/WALK.",
                "",
                "| Modelo | Maquina planejada | IP | Motivo |",
                "| --- | --- | --- | --- |",
            ]
        )
        for target in report.get("alvos_planejados", []):
            lines.append(
                "| {modelo} | {maquina} | {ip} | {motivo} |".format(
                    modelo=f"{target.get('fabricante')} {target.get('modelo')}",
                    maquina=target.get("maquina") or "-",
                    ip=target.get("ip") or "-",
                    motivo=target.get("motivo_ignorado") or "planejado",
                )
            )
        return "\n".join(lines) + "\n"

    for result in report.get("resultados", []):
        get_result = result.get("get_alert_raw") or {}
        lines.extend(
            [
                f"## {result.get('fabricante')} {result.get('modelo')}",
                "",
                "| Campo | Valor |",
                "| --- | --- |",
                f"| Modelo | {result.get('fabricante')} {result.get('modelo')} |",
                f"| Maquina | {result.get('maquina') or '-'} |",
                f"| IP | {result.get('ip') or '-'} |",
                f"| Online antes da coleta? | {result.get('online_antes_da_coleta')} |",
                f"| GET alert_raw retornou? | {get_result.get('sucesso') if get_result else False} |",
                f"| Quantidade de valores no GET | {get_result.get('quantidade_valores', 0) if get_result else 0} |",
                f"| WALK prtAlertDescription retornou quantos? | {_count_walk(result, 'prtAlertDescription')} |",
                f"| WALK hrPrinterStatus retornou quantos? | {_count_walk(result, 'hrPrinterStatus')} |",
                f"| WALK hrPrinterDetectedErrorState retornou quantos? | {_count_walk(result, 'hrPrinterDetectedErrorState')} |",
                f"| Conclusao preliminar | {result.get('conclusao_preliminar')} |",
                "",
            ]
        )
    return "\n".join(lines)


def write_reports(
    report: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    timestamp: datetime | None = None,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"diagnostico_snmp_alertas_{stamp}.json"
    md_path = output_dir / f"diagnostico_snmp_alertas_{stamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    md_path.write_text(build_markdown(report), encoding="utf-8")
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostica GET x WALK para alertas SNMP de impressoras reais."
    )
    parser.add_argument("--confirmar", action="store_true", help="Executa consultas reais.")
    parser.add_argument("--modelo", help="Filtra por fabricante/modelo.")
    parser.add_argument("--maquina-id", type=int, help="Filtra por maquina especifica.")
    parser.add_argument(
        "--todas",
        action="store_true",
        help="Testa todas as maquinas ativas de cada modelo em vez de uma por modelo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_monitoring_settings()
    db = SessionLocal()
    try:
        rows = load_candidate_rows(
            db,
            modelo_filter=args.modelo,
            maquina_id=args.maquina_id,
        )
        targets = select_diagnostic_targets(rows, testar_todas=args.todas)
        report = build_report(
            targets=targets,
            confirmar=args.confirmar,
            settings=settings,
        )
        if args.confirmar:
            json_path, md_path = write_reports(report)
            emitir(f"Diagnostico gerado: {json_path}")
            emitir(f"Resumo gerado: {md_path}")
        else:
            emitir(build_markdown(report))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
