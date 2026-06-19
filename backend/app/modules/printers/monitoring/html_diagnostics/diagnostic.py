"""Diagnostico seguro de caminhos HTML cadastrados por modelo."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.app.modules.printers.machines.models import PrinterMachine, PrinterModel
from backend.app.modules.printers.monitoring.html_client.client import fetch_html_page
from backend.app.modules.printers.monitoring.html_client.models import (
    HtmlAccessConfig,
    HtmlClientResponse,
)
from backend.app.modules.printers.monitoring.html_credentials.crypto import (
    decrypt_password,
)
from backend.app.modules.printers.monitoring.html_credentials.models import (
    PrinterCollectionCredential,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    extract_visible_text_chunks,
)
from backend.app.modules.printers.monitoring.html_parsers.registry import (
    get_status_parser_for_model,
    parse_html_status_response,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text
from backend.app.modules.printers.status.models import StatusImpressora


OUTPUT_DIR = Path("tmp/diagnosticos/html_modelos")
INFORMATION_CAPABILITIES = {
    "modelo": ("modelo", "model"),
    "numero_serie": ("numero de serie", "numero serie", "serial", "serial number"),
    "firmware": ("firmware", "versao firmware", "main firmware"),
    "contador_total": ("contador", "contador total", "page count", "total pages"),
    "toner": ("toner", "cartucho", "cartridge"),
    "tambor": ("tambor", "drum"),
    "papel": ("papel", "paper"),
    "bandejas": ("bandeja", "bandejas", "tray", "trays"),
    "paginas_por_tamanho": ("a4", "letter", "tamanho", "page size"),
    "paginas_por_tipo": ("duplex", "simplex", "mono", "color", "tipo"),
    "digitalizacoes": ("digitalizacao", "digitalizacoes", "scan", "scanner"),
    "erros": ("erro", "erros", "error", "warning", "alert"),
}
UNSUPPORTED_AUTH_TYPES = {"form", "cookie"}
SENSITIVE_MARKERS = (
    "senha",
    "password",
    "authorization",
    "cookie",
    "csrf",
    "senha_criptografada",
)


@dataclass(frozen=True)
class HtmlDiagnosticTarget:
    modelo_id: int
    fabricante: str
    modelo: str
    tipo_autenticacao: str
    usuario: str | None
    senha: str | None = field(repr=False)
    caminho_status: str | None
    caminho_informacoes: str | None
    caminho_login: str | None
    timeout_segundos: int
    protocolo_preferencial: str
    validar_ssl: bool
    maquina_id: int | None
    maquina: str | None
    ip: str | None
    status_previo: str | None = None
    motivo_ignorado: str | None = None

    def safe_dict(self) -> dict[str, Any]:
        parser = get_status_parser_for_model(
            {"manufacturer": self.fabricante, "name": self.modelo}
        )
        return {
            "modelo_id": self.modelo_id,
            "fabricante": self.fabricante,
            "modelo": self.modelo,
            "maquina_id": self.maquina_id,
            "maquina": self.maquina,
            "ip": self.ip,
            "status_previo": self.status_previo,
            "motivo_ignorado": self.motivo_ignorado,
            "caminho_status": self.caminho_status,
            "caminho_informacoes": self.caminho_informacoes,
            "caminho_login_configurado": bool(self.caminho_login),
            "tipo_autenticacao": self.tipo_autenticacao,
            "usuario_configurado": bool(self.usuario),
            "protocolo_preferencial": self.protocolo_preferencial,
            "validar_ssl": self.validar_ssl,
            "timeout_segundos": self.timeout_segundos,
            "parser_status": "disponivel" if parser else "sem_parser",
        }


def sanitize_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    sanitized = value
    for marker in SENSITIVE_MARKERS:
        sanitized = sanitized.replace(marker, f"[{marker}_oculto]")
        sanitized = sanitized.replace(marker.upper(), f"[{marker}_oculto]")
        sanitized = sanitized.replace(marker.title(), f"[{marker}_oculto]")
    return sanitized[:1000]


def sanitize_payload(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: sanitize_payload(value)
            for key, value in data.items()
            if normalize_text(key) not in {"senha", "senha criptografada", "password"}
        }
    if isinstance(data, list):
        return [sanitize_payload(item) for item in data]
    return sanitize_text(data)


def _safe_bool(value: Any) -> bool:
    return bool(value)


def detect_information_capabilities(html: str) -> dict[str, bool]:
    chunks = extract_visible_text_chunks(html or "")
    normalized_text = normalize_text(" ".join(chunks))
    return {
        capability: any(normalize_text(term) in normalized_text for term in terms)
        for capability, terms in INFORMATION_CAPABILITIES.items()
    }


def target_to_config(target: HtmlDiagnosticTarget) -> HtmlAccessConfig:
    return HtmlAccessConfig(
        modelo_id=target.modelo_id,
        tipo_autenticacao=target.tipo_autenticacao,
        usuario=target.usuario,
        senha=target.senha,
        caminho_status=target.caminho_status,
        caminho_informacoes=target.caminho_informacoes,
        caminho_login=target.caminho_login,
        timeout_segundos=target.timeout_segundos,
        protocolo_preferencial=target.protocolo_preferencial,
        validar_ssl=target.validar_ssl,
    )


def load_candidate_rows(
    db: Session,
    *,
    modelo_filter: str | None = None,
    maquina_id: int | None = None,
) -> list[dict[str, Any]]:
    models = PrinterModel.__table__
    machines = PrinterMachine.__table__
    credentials = PrinterCollectionCredential.__table__
    statuses = StatusImpressora.__table__

    query = (
        select(
            models.c.id.label("modelo_id"),
            models.c.manufacturer.label("fabricante"),
            models.c.name.label("modelo"),
            credentials.c.tipo_autenticacao,
            credentials.c.usuario,
            credentials.c.senha_criptografada,
            credentials.c.caminho_status,
            credentials.c.caminho_informacoes,
            credentials.c.caminho_login,
            credentials.c.timeout_segundos,
            credentials.c.protocolo_preferencial,
            credentials.c.validar_ssl,
            machines.c.id.label("maquina_id"),
            machines.c.name.label("maquina"),
            machines.c.ip_address.label("ip"),
            machines.c.is_active.label("maquina_ativa"),
            statuses.c.status_operacional.label("status_previo"),
        )
        .select_from(
            credentials.join(models, credentials.c.modelo_id == models.c.id)
            .outerjoin(machines, machines.c.model_id == models.c.id)
            .outerjoin(statuses, statuses.c.maquina_id == machines.c.id)
        )
        .where(credentials.c.ativo.is_(True))
        .order_by(models.c.manufacturer.asc(), models.c.name.asc(), machines.c.id.asc())
    )
    if maquina_id is not None:
        query = query.where(machines.c.id == maquina_id)

    rows = [dict(row._mapping) for row in db.execute(query).all()]
    return filter_candidate_rows(rows, modelo_filter=modelo_filter, maquina_id=maquina_id)


def filter_candidate_rows(
    rows: Iterable[dict[str, Any]],
    *,
    modelo_filter: str | None = None,
    maquina_id: int | None = None,
) -> list[dict[str, Any]]:
    filtered_rows = list(rows)
    if maquina_id is not None:
        filtered_rows = [
            row for row in filtered_rows if int(row.get("maquina_id") or 0) == maquina_id
        ]
    if modelo_filter:
        needle = normalize_text(modelo_filter)
        filtered_rows = [
            row
            for row in filtered_rows
            if needle in normalize_text(f"{row['fabricante']} {row['modelo']}")
        ]
    return filtered_rows


def _row_is_eligible(row: dict[str, Any], *, incluir_offline: bool) -> bool:
    if row.get("maquina_id") is None:
        return False
    if row.get("maquina_ativa") is False:
        return False
    if not str(row.get("ip") or "").strip():
        return False
    if not incluir_offline and normalize_text(row.get("status_previo")) == "offline":
        return False
    return True


def _row_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    online_priority = 0 if normalize_text(row.get("status_previo")) == "online" else 1
    return online_priority, int(row.get("maquina_id") or 0)


def _target_from_row(row: dict[str, Any], *, motivo_ignorado: str | None = None) -> HtmlDiagnosticTarget:
    password = None
    if row.get("senha_criptografada"):
        password = decrypt_password(row["senha_criptografada"])
    return HtmlDiagnosticTarget(
        modelo_id=int(row["modelo_id"]),
        fabricante=row["fabricante"],
        modelo=row["modelo"],
        tipo_autenticacao=row["tipo_autenticacao"],
        usuario=row.get("usuario"),
        senha=password,
        caminho_status=row.get("caminho_status"),
        caminho_informacoes=row.get("caminho_informacoes"),
        caminho_login=row.get("caminho_login"),
        timeout_segundos=int(row.get("timeout_segundos") or 5),
        protocolo_preferencial=row.get("protocolo_preferencial") or "auto",
        validar_ssl=bool(row.get("validar_ssl")),
        maquina_id=row.get("maquina_id"),
        maquina=row.get("maquina"),
        ip=row.get("ip"),
        status_previo=row.get("status_previo"),
        motivo_ignorado=motivo_ignorado,
    )


def select_diagnostic_targets(
    rows: Iterable[dict[str, Any]],
    *,
    incluir_offline: bool = False,
) -> list[HtmlDiagnosticTarget]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["modelo_id"]), []).append(row)

    targets: list[HtmlDiagnosticTarget] = []
    for model_id in sorted(grouped):
        candidates = grouped[model_id]
        eligible = [
            row for row in candidates if _row_is_eligible(row, incluir_offline=incluir_offline)
        ]
        if not eligible:
            targets.append(
                _target_from_row(
                    candidates[0],
                    motivo_ignorado="html_modelo_sem_maquina_elegivel",
                )
            )
            continue
        targets.append(_target_from_row(sorted(eligible, key=_row_sort_key)[0]))
    return targets


def dry_run_report(targets: list[HtmlDiagnosticTarget], *, timestamp: datetime) -> dict[str, Any]:
    return sanitize_payload(
        {
            "executado": False,
            "modo": "dry_run",
            "gerado_em": timestamp.isoformat(timespec="seconds"),
            "mensagem": "Use --confirmar para consultar paineis HTML reais.",
            "alvos_planejados": [target.safe_dict() for target in targets],
            "matriz_modelos": build_model_matrix([], targets=targets),
        }
    )


def unsupported_auth_result(
    target: HtmlDiagnosticTarget,
    *,
    test_type: str,
    path: str | None,
) -> dict[str, Any]:
    return {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina": target.maquina,
        "ip": target.ip,
        "tipo_teste": test_type,
        "caminho": path,
        "autenticacao": target.tipo_autenticacao,
        "sucesso": False,
        "erro_codigo": "autenticacao_nao_suportada_nesta_etapa",
        "erro_detalhe_sanitizado": "Autenticacao form/cookie ainda nao suportada.",
    }


def _client_error_code(response: HtmlClientResponse) -> str | None:
    if response.erro_codigo == "falha_requisicao_html":
        return "html_requisicao_falhou"
    return response.erro_codigo


def diagnose_status_path(
    target: HtmlDiagnosticTarget,
    *,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    if target.motivo_ignorado:
        return {
            "tipo_teste": "status",
            "sucesso": False,
            "erro_codigo": target.motivo_ignorado,
        }
    if not target.caminho_status:
        return {
            "tipo_teste": "status",
            "sucesso": False,
            "erro_codigo": "html_caminho_status_nao_configurado",
        }
    if target.tipo_autenticacao in UNSUPPORTED_AUTH_TYPES:
        return unsupported_auth_result(target, test_type="status", path=target.caminho_status)

    response = fetcher(target.ip, target_to_config(target), page_type="status")
    base = {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina": target.maquina,
        "ip": target.ip,
        "tipo_teste": "status",
        "caminho": target.caminho_status,
        "protocolo_usado": response.protocolo_usado,
        "status_code": response.status_code,
        "autenticacao": target.tipo_autenticacao,
        "html_recebido": bool(response.conteudo_html),
    }
    if not response.sucesso:
        return {
            **base,
            "parser_status": "nao_executado",
            "estado_detectado": False,
            "sucesso": False,
            "erro_codigo": _client_error_code(response) or "html_requisicao_falhou",
            "erro_detalhe_sanitizado": response.erro_detalhe_sanitizado,
        }
    if not response.conteudo_html:
        return {
            **base,
            "parser_status": "nao_executado",
            "estado_detectado": False,
            "sucesso": False,
            "erro_codigo": "html_conteudo_vazio",
        }

    parser = get_status_parser_for_model(
        {"manufacturer": target.fabricante, "name": target.modelo}
    )
    if parser is None:
        return {
            **base,
            "parser_status": "sem_parser",
            "estado_detectado": False,
            "sucesso": False,
            "erro_codigo": "html_parser_nao_configurado",
        }

    parse_result = parse_html_status_response(
        {"manufacturer": target.fabricante, "name": target.modelo},
        response,
    )
    return {
        **base,
        "parser_status": "disponivel",
        "estado_detectado": parse_result.sucesso,
        "estado_principal": parse_result.estado_principal,
        "mensagens_brutas": parse_result.mensagens_brutas,
        "mensagens_normalizadas": parse_result.mensagens_normalizadas,
        "sucesso": bool(parse_result.sucesso),
        "erro_codigo": None if parse_result.sucesso else "html_status_nao_detectado",
        "erro_detalhe_sanitizado": parse_result.erro_detalhe_sanitizado,
    }


def diagnose_information_path(
    target: HtmlDiagnosticTarget,
    *,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    if target.motivo_ignorado:
        return {
            "tipo_teste": "informacoes",
            "sucesso": False,
            "erro_codigo": target.motivo_ignorado,
        }
    if not target.caminho_informacoes:
        return {
            "tipo_teste": "informacoes",
            "sucesso": False,
            "erro_codigo": "html_caminho_informacoes_nao_configurado",
        }
    if target.tipo_autenticacao in UNSUPPORTED_AUTH_TYPES:
        return unsupported_auth_result(
            target,
            test_type="informacoes",
            path=target.caminho_informacoes,
        )

    response = fetcher(target.ip, target_to_config(target), page_type="informacoes")
    base = {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina": target.maquina,
        "ip": target.ip,
        "tipo_teste": "informacoes",
        "caminho": target.caminho_informacoes,
        "protocolo_usado": response.protocolo_usado,
        "status_code": response.status_code,
        "autenticacao": target.tipo_autenticacao,
        "html_recebido": bool(response.conteudo_html),
    }
    if not response.sucesso:
        return {
            **base,
            "capacidades_detectadas": {},
            "sucesso": False,
            "erro_codigo": _client_error_code(response) or "html_requisicao_falhou",
            "erro_detalhe_sanitizado": response.erro_detalhe_sanitizado,
        }
    if not response.conteudo_html:
        return {
            **base,
            "capacidades_detectadas": {},
            "sucesso": False,
            "erro_codigo": "html_conteudo_vazio",
        }

    capabilities = detect_information_capabilities(response.conteudo_html)
    success = any(capabilities.values())
    return {
        **base,
        "capacidades_detectadas": capabilities,
        "sucesso": success,
        "erro_codigo": None if success else "html_capacidades_nao_detectadas",
    }


def diagnose_target(
    target: HtmlDiagnosticTarget,
    *,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    return {
        "modelo_id": target.modelo_id,
        "fabricante": target.fabricante,
        "modelo": target.modelo,
        "maquina_id": target.maquina_id,
        "maquina": target.maquina,
        "ip": target.ip,
        "status_previo": target.status_previo,
        "caminho_login_configurado": bool(target.caminho_login),
        "login_observacao": (
            "login_form_nao_implementado"
            if target.tipo_autenticacao in UNSUPPORTED_AUTH_TYPES
            else "nao_usado_para_basic_digest"
        ),
        "status": diagnose_status_path(target, fetcher=fetcher),
        "informacoes": diagnose_information_path(target, fetcher=fetcher),
    }


def build_model_matrix(
    results: list[dict[str, Any]],
    *,
    targets: list[HtmlDiagnosticTarget] | None = None,
) -> list[dict[str, Any]]:
    if targets is not None and not results:
        return [
            {
                "modelo": f"{target.fabricante} {target.modelo}",
                "status_html": "a_confirmar" if target.caminho_status else "nao_configurado",
                "informacoes_html": (
                    "a_confirmar" if target.caminho_informacoes else "nao_configurado"
                ),
                "parser_status": target.safe_dict()["parser_status"],
                "capacidade_informacoes": "a_confirmar",
            }
            for target in targets
        ]

    matrix = []
    for result in results:
        status = result.get("status") or {}
        info = result.get("informacoes") or {}
        capabilities = info.get("capacidades_detectadas") or {}
        detected_count = sum(1 for detected in capabilities.values() if detected)
        matrix.append(
            {
                "modelo": f"{result.get('fabricante')} {result.get('modelo')}",
                "status_html": "OK" if status.get("sucesso") else status.get("erro_codigo"),
                "informacoes_html": "OK" if info.get("sucesso") else info.get("erro_codigo"),
                "parser_status": status.get("parser_status") or "sem_parser",
                "capacidade_informacoes": (
                    "OK"
                    if detected_count >= 6
                    else "parcial"
                    if detected_count > 0
                    else "falha"
                ),
            }
        )
    return matrix


def build_report(
    *,
    targets: list[HtmlDiagnosticTarget],
    confirmar: bool,
    fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    generated_at = timestamp or datetime.now()
    if not confirmar:
        return dry_run_report(targets, timestamp=generated_at)

    results = [diagnose_target(target, fetcher=fetcher) for target in targets]
    return sanitize_payload(
        {
            "executado": True,
            "modo": "confirmado",
            "gerado_em": generated_at.isoformat(timespec="seconds"),
            "resultados": results,
            "matriz_modelos": build_model_matrix(results),
        }
    )


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Diagnostico HTML por modelo",
        "",
        f"- Gerado em: {report.get('gerado_em')}",
        f"- Modo: {report.get('modo')}",
        "",
        "| Modelo | Status HTML | Informacoes HTML | Parser status | Capacidade informacoes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report.get("matriz_modelos", []):
        lines.append(
            "| {modelo} | {status_html} | {informacoes_html} | {parser_status} | {capacidade_informacoes} |".format(
                **row
            )
        )
    if not report.get("executado"):
        lines.extend(
            [
                "",
                "## Dry-run",
                "",
                "Nenhuma requisicao HTTP real foi executada.",
                "",
                "| Modelo | Maquina | IP | Status | Informacoes | Autenticacao | Parser |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for target in report.get("alvos_planejados", []):
            lines.append(
                "| {modelo} | {maquina} | {ip} | {caminho_status} | {caminho_informacoes} | {tipo_autenticacao} | {parser_status} |".format(
                    modelo=f"{target.get('fabricante')} {target.get('modelo')}",
                    maquina=target.get("maquina") or "-",
                    ip=target.get("ip") or "-",
                    caminho_status=target.get("caminho_status") or "-",
                    caminho_informacoes=target.get("caminho_informacoes") or "-",
                    tipo_autenticacao=target.get("tipo_autenticacao") or "-",
                    parser_status=target.get("parser_status") or "-",
                )
            )
    return "\n".join(lines) + "\n"


def write_reports(
    report: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    write_json: bool = True,
    write_md: bool = True,
    timestamp: datetime | None = None,
) -> tuple[Path | None, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"diagnostico_html_modelos_{stamp}.json"
    md_path = output_dir / f"diagnostico_html_modelos_{stamp}.md"
    if write_json:
        json_path.write_text(
            json.dumps(sanitize_payload(report), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    else:
        json_path = None
    if write_md:
        md_path.write_text(build_markdown(sanitize_payload(report)), encoding="utf-8")
    else:
        md_path = None
    return json_path, md_path
