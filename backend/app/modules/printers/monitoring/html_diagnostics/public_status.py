"""Diagnostico opt-in do status publico Brother DCP-L1632W."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests
from requests import RequestException

from backend.app.modules.printers.monitoring.html_client.client import (
    build_html_url,
    fetch_html_page,
    protocol_sequence,
)
from backend.app.modules.printers.monitoring.html_client.models import HtmlClientResponse
from backend.app.modules.printers.monitoring.html_diagnostics.diagnostic import (
    OUTPUT_DIR,
    HtmlDiagnosticTarget,
    detect_information_capabilities,
    sanitize_payload,
    sanitized_machine_label,
    target_to_config,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    build_brother_l1632w_maintenance_debug,
    build_brother_l1632w_moni_data_debug,
    classify_brother_html_auth_state,
    detect_brother_l1632w_maintenance_markers,
    parse_brother_dcp_l1632w_maintenance_info,
)
from backend.app.modules.printers.monitoring.html_parsers.registry import (
    parse_status_html_for_model,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


PUBLIC_STATUS_REPORT_PREFIX = "diagnostico_brother_l1632w_public_status"


@dataclass(frozen=True)
class PublicStatusHttpResult:
    sucesso: bool
    status_code: int | None
    conteudo: str | None
    protocolo_usado: str | None
    erro_codigo: str | None = None
    erro_detalhe_sanitizado: str | None = None


def _is_brother_l1632w(target: HtmlDiagnosticTarget) -> bool:
    return (
        normalize_text(target.fabricante),
        normalize_text(target.modelo),
    ) == ("brother", "dcp-l1632w")


def fetch_public_status_page(
    target: HtmlDiagnosticTarget,
    session,
) -> PublicStatusHttpResult:
    if not target.caminho_status:
        return PublicStatusHttpResult(
            sucesso=False,
            status_code=None,
            conteudo=None,
            protocolo_usado=None,
            erro_codigo="html_caminho_status_nao_configurado",
        )

    config = target_to_config(target)
    last_error: PublicStatusHttpResult | None = None
    for protocol in protocol_sequence(config.protocolo_preferencial):
        try:
            url = build_html_url(
                target.ip or "",
                protocol,
                target.caminho_status,
                port=config.porta,
            )
            response = session.get(
                url,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
        except (RequestException, ValueError) as exc:
            last_error = PublicStatusHttpResult(
                sucesso=False,
                status_code=None,
                conteudo=None,
                protocolo_usado=protocol,
                erro_codigo="falha_requisicao_status_publico",
                erro_detalhe_sanitizado=exc.__class__.__name__,
            )
            continue

        success = 200 <= response.status_code < 400
        return PublicStatusHttpResult(
            sucesso=success,
            status_code=response.status_code,
            conteudo=response.text if success else None,
            protocolo_usado=protocol,
            erro_codigo=None if success else "http_status_sem_sucesso",
            erro_detalhe_sanitizado=None if success else f"HTTP {response.status_code}",
        )

    return last_error or PublicStatusHttpResult(
        sucesso=False,
        status_code=None,
        conteudo=None,
        protocolo_usado=None,
        erro_codigo="falha_requisicao_status_publico",
        erro_detalhe_sanitizado="Falha ao consultar status publico.",
    )


def diagnose_public_status_path(
    target: HtmlDiagnosticTarget,
    *,
    public_fetcher: Callable[[HtmlDiagnosticTarget, Any], PublicStatusHttpResult] = fetch_public_status_page,
) -> dict[str, Any]:
    session = requests.Session()
    response = public_fetcher(target, session)
    html = response.conteudo or ""
    moni_data_debug = build_brother_l1632w_moni_data_debug(html)
    auth_state = classify_brother_html_auth_state(html)

    base = {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina_sanitizada": sanitized_machine_label(target),
        "caminho": target.caminho_status,
        "status_http": response.status_code,
        "protocolo_usado": response.protocolo_usado,
        "origem": "html_publico",
        "autenticacao_usada": False,
        "login_executado": False,
        "post_executado": False,
        "cookie_autenticado_usado": False,
        "auth_state": auth_state,
        "moni_data_debug": moni_data_debug,
    }
    if not response.sucesso:
        return {
            **base,
            "sucesso": False,
            "estado_principal": None,
            "mensagens_brutas": [],
            "mensagens_normalizadas": [],
            "erro_codigo": response.erro_codigo or "html_status_publico_nao_detectado",
            "erro_detalhe_sanitizado": response.erro_detalhe_sanitizado,
            "causa_sanitizada": "falha_requisicao_status_publico",
        }

    parse_result = parse_status_html_for_model(
        {"manufacturer": target.fabricante, "name": target.modelo},
        html,
    )
    if parse_result.sucesso:
        return {
            **base,
            "sucesso": True,
            "estado_principal": parse_result.estado_principal,
            "mensagens_brutas": parse_result.mensagens_brutas,
            "mensagens_normalizadas": parse_result.mensagens_normalizadas,
            "erro_codigo": None,
            "erro_detalhe_sanitizado": None,
            "causa_sanitizada": None,
        }

    if moni_data_debug["tem_moni_data"] and moni_data_debug["parece_vazio"]:
        error_code = "html_status_publico_vazio"
        cause = "moni_data_vazio_sem_login"
    elif not moni_data_debug["tem_moni_data"]:
        error_code = "html_status_publico_nao_detectado"
        cause = "moni_data_ausente_sem_login"
    else:
        error_code = "html_status_publico_nao_detectado"
        cause = "texto_operacional_publico_nao_detectado"

    return {
        **base,
        "sucesso": False,
        "estado_principal": None,
        "mensagens_brutas": [],
        "mensagens_normalizadas": [],
        "erro_codigo": error_code,
        "erro_detalhe_sanitizado": "Estado publico nao encontrado no HTML de status.",
        "causa_sanitizada": cause,
    }


def diagnose_authenticated_maintenance_path(
    target: HtmlDiagnosticTarget,
    *,
    maintenance_fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    session = requests.Session()
    response = maintenance_fetcher(
        target.ip,
        target_to_config(target),
        page_type="informacoes",
        session=session,
    )
    html = response.conteudo_html or ""
    capabilities = detect_information_capabilities(html)
    maintenance_info = parse_brother_dcp_l1632w_maintenance_info(html) if html else {}
    maintenance_state = detect_brother_l1632w_maintenance_markers(html) if html else {}
    maintenance_debug = build_brother_l1632w_maintenance_debug(html) if html else {}
    return {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina_sanitizada": sanitized_machine_label(target),
        "caminho": target.caminho_informacoes,
        "status_http": response.status_code,
        "autenticacao_usada": target.tipo_autenticacao in {"basic", "digest", "form"},
        "login_executado": bool((response.metadados or {}).get("post_executado")),
        "diagnostico_login": response.metadados or {},
        "capacidades_detectadas": capabilities,
        "maintenance_state": maintenance_state,
        "maintenance_debug": maintenance_debug,
        "maintenance_info": maintenance_info,
        "sucesso": bool(response.sucesso and (any(capabilities.values()) or maintenance_info)),
        "erro_codigo": None if response.sucesso else response.erro_codigo,
        "erro_detalhe_sanitizado": response.erro_detalhe_sanitizado,
    }


def _final_decision(status_result: dict[str, Any]) -> dict[str, str]:
    if status_result.get("sucesso"):
        return {
            "status": "resolvida",
            "mensagem": (
                "Brother DCP-L1632W resolvida para status HTML publico. "
                "A integracao futura do HTML publico como fallback permanece fora desta etapa."
            ),
            "proxima_etapa": "preparar integracao futura do HTML publico como fallback, sem integrar agora",
        }
    return {
        "status": "pendencia_tecnica_nao_bloqueante",
        "mensagem": (
            "Brother DCP-L1632W ficara como pendencia tecnica nao bloqueante. "
            "Nao continuar investigando este modelo agora."
        ),
        "proxima_etapa": "avancar para os outros modelos de impressora",
    }


def diagnose_public_status_target(
    target: HtmlDiagnosticTarget,
    *,
    public_fetcher: Callable[[HtmlDiagnosticTarget, Any], PublicStatusHttpResult] = fetch_public_status_page,
    maintenance_fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
) -> dict[str, Any]:
    if target.motivo_ignorado:
        return sanitize_payload(
            {
                "modelo": f"{target.fabricante} {target.modelo}",
                "maquina_sanitizada": sanitized_machine_label(target),
                "sucesso": False,
                "erro_codigo": target.motivo_ignorado,
            }
        )
    if not _is_brother_l1632w(target):
        return sanitize_payload(
            {
                "modelo": f"{target.fabricante} {target.modelo}",
                "maquina_sanitizada": sanitized_machine_label(target),
                "sucesso": False,
                "erro_codigo": "diagnostico_status_publico_modelo_nao_suportado",
            }
        )

    status_result = diagnose_public_status_path(target, public_fetcher=public_fetcher)
    maintenance_result = diagnose_authenticated_maintenance_path(
        target,
        maintenance_fetcher=maintenance_fetcher,
    )
    return sanitize_payload(
        {
            "modelo": f"{target.fabricante} {target.modelo}",
            "maquina_sanitizada": sanitized_machine_label(target),
            "status_publico": status_result,
            "manutencao": maintenance_result,
            "decisao_final": _final_decision(status_result),
        }
    )


def build_public_status_report(
    *,
    targets: list[HtmlDiagnosticTarget],
    confirmar: bool,
    public_fetcher: Callable[[HtmlDiagnosticTarget, Any], PublicStatusHttpResult] = fetch_public_status_page,
    maintenance_fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    generated_at = timestamp or datetime.now()
    if not confirmar:
        return sanitize_payload(
            {
                "executado": False,
                "modo": "dry_run_status_publico",
                "gerado_em": generated_at.isoformat(timespec="seconds"),
                "mensagem": "Use --confirmar para consultar status publico real.",
                "alvos_planejados": [target.safe_dict() for target in targets],
            }
        )
    return sanitize_payload(
        {
            "executado": True,
            "modo": "confirmado_status_publico",
            "gerado_em": generated_at.isoformat(timespec="seconds"),
            "resultados": [
                diagnose_public_status_target(
                    target,
                    public_fetcher=public_fetcher,
                    maintenance_fetcher=maintenance_fetcher,
                )
                for target in targets
            ],
        }
    )


def build_public_status_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Diagnostico status publico Brother DCP-L1632W",
        "",
        f"- Gerado em: {report.get('gerado_em')}",
        f"- Modo: {report.get('modo')}",
        "",
    ]
    for result in report.get("resultados", []):
        status = result.get("status_publico") or {}
        maintenance = result.get("manutencao") or {}
        decision = result.get("decisao_final") or {}
        lines.extend(
            [
                f"## {result.get('modelo')}",
                "",
                f"- Maquina: {result.get('maquina_sanitizada')}",
                f"- Status publico: {status.get('erro_codigo') or 'OK'}",
                f"- Autenticacao no status: {status.get('autenticacao_usada')}",
                f"- Estado principal: {status.get('estado_principal') or '-'}",
                f"- Manutencao autenticada: {maintenance.get('autenticacao_usada')}",
                f"- Campos de manutencao: {maintenance.get('maintenance_info') or {}}",
                f"- Decisao: {decision.get('status') or '-'}",
                f"- Proxima etapa: {decision.get('proxima_etapa') or '-'}",
                "",
            ]
        )
    if not report.get("executado"):
        lines.append("Nenhuma requisicao HTTP real foi executada.")
        lines.append("")
    return "\n".join(lines)


def write_public_status_reports(
    report: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    write_json: bool = True,
    write_md: bool = True,
    timestamp: datetime | None = None,
) -> tuple[Path | None, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"{PUBLIC_STATUS_REPORT_PREFIX}_{stamp}.json"
    md_path = output_dir / f"{PUBLIC_STATUS_REPORT_PREFIX}_{stamp}.md"
    if write_json:
        json_path.write_text(
            json.dumps(sanitize_payload(report), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    else:
        json_path = None
    if write_md:
        md_path.write_text(
            build_public_status_markdown(sanitize_payload(report)),
            encoding="utf-8",
        )
    else:
        md_path = None
    return json_path, md_path
