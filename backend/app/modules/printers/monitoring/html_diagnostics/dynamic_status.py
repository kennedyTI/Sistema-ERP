"""Diagnostico opt-in da atualizacao dinamica de status Brother."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import requests
from requests import RequestException

from backend.app.modules.printers.monitoring.html_client.client import (
    build_auth,
    build_html_url,
    fetch_html_page,
)
from backend.app.modules.printers.monitoring.html_client.models import (
    HtmlClientResponse,
)
from backend.app.modules.printers.monitoring.html_diagnostics.diagnostic import (
    OUTPUT_DIR,
    HtmlDiagnosticTarget,
    sanitize_payload,
    sanitized_machine_label,
    target_to_config,
)
from backend.app.modules.printers.monitoring.html_parsers.brother import (
    build_brother_l1632w_moni_data_debug,
    classify_brother_html_auth_state,
    detect_brother_l1632w_status_terms,
)
from backend.app.modules.printers.monitoring.state.rules import normalize_text


DYNAMIC_REPORT_PREFIX = "diagnostico_brother_l1632w_dynamic_status"
JS_SEARCH_TERMS = (
    "moni_data",
    "moni",
    "refreshLCD",
    "judge_refresh",
    "XMLHttpRequest",
    "fetch",
    "ajax",
    "GET",
    "POST",
    "status",
    "lcd",
    "display",
    "home/status",
    "reflesh",
    "refresh",
    "pageid",
    "CSRFToken",
)
JS_FUNCTION_TERMS = (
    "refreshLCD",
    "judge_refresh",
    "XMLHttpRequest",
    "fetch",
    "ajax",
)
JS_PARAM_TERMS = ("pageid", "Refresh", "CSRFToken")
SAFE_DYNAMIC_ENDPOINT_TERMS = (
    "status",
    "lcd",
    "display",
    "refresh",
    "reflesh",
    "moni",
    "home/status",
)
BLOCKED_DYNAMIC_PREFIXES = (
    "/admin/",
    "/net/",
    "/copy/",
    "/print/",
    "/scan/",
    "/onlinefunctions/",
)


@dataclass(frozen=True)
class DynamicHttpResult:
    sucesso: bool
    status_code: int | None
    conteudo: str | None
    erro_codigo: str | None = None
    erro_detalhe_sanitizado: str | None = None


class BrotherScriptReferenceParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.scripts: list[str] = []
        self.inline_scripts: list[str] = []
        self._inside_script = False
        self._inline_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() != "script":
            return
        attributes = {key.lower(): value or "" for key, value in attrs}
        src = sanitize_relative_asset_path(attributes.get("src"))
        if src:
            self.scripts.append(src)
        self._inside_script = True
        self._inline_chunks = []

    def handle_data(self, data: str):
        if self._inside_script and data:
            self._inline_chunks.append(data)

    def handle_endtag(self, tag: str):
        if tag.lower() != "script" or not self._inside_script:
            return
        inline = "\n".join(self._inline_chunks).strip()
        if inline:
            self.inline_scripts.append(inline)
        self._inside_script = False
        self._inline_chunks = []


def _unique(values: list[str], *, limit: int = 20) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not value or normalized in seen:
            continue
        result.append(value)
        seen.add(normalized)
        if len(result) >= limit:
            break
    return result


def sanitize_relative_asset_path(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw or any(char in raw for char in ("\r", "\n", "\t", "\\")):
        return None
    parsed = urlsplit(raw)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.scheme or parsed.netloc:
        path = parsed.path
    elif raw.startswith("/"):
        path = parsed.path
    else:
        path = f"/{parsed.path.lstrip('./')}"
    if not path or not path.startswith("/"):
        return None
    if parsed.query:
        return f"{path}?{parsed.query}"
    return path


def extract_script_references(html: str | None) -> dict[str, list[str]]:
    parser = BrotherScriptReferenceParser()
    parser.feed(html or "")
    parser.close()
    return {
        "scripts_detectados": _unique(parser.scripts),
        "scripts_inline": [f"inline_status_{index}" for index, _script in enumerate(parser.inline_scripts, start=1)],
        "_inline_raw": parser.inline_scripts,
    }


def _candidate_paths_from_js(script: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"""["']([^"']{1,180})["']""", script or ""):
        value = match.group(1).strip()
        if not (
            value.startswith("/")
            or value.startswith("http://")
            or value.startswith("https://")
            or value.startswith("//")
        ):
            continue
        path = sanitize_relative_asset_path(value)
        if path:
            candidates.append(path)
    return _unique(candidates)


def _methods_from_js(script: str) -> list[str]:
    methods: list[str] = []
    for match in re.finditer(r"""\b(?:open|method)\s*\(?\s*["'](GET|POST)["']""", script or "", re.IGNORECASE):
        methods.append(match.group(1).upper())
    for method in ("GET", "POST"):
        if re.search(rf"""["']{method}["']""", script or "", re.IGNORECASE):
            methods.append(method)
    return _unique(methods, limit=4)


def analyze_dynamic_script(script: str | None, *, script_path: str) -> dict[str, Any]:
    content = script or ""
    lowered = content.casefold()
    terms = [term for term in JS_SEARCH_TERMS if term.casefold() in lowered]
    functions = [term for term in JS_FUNCTION_TERMS if term.casefold() in lowered]
    endpoints = _candidate_paths_from_js(content)
    methods = _methods_from_js(content)
    params = [term for term in JS_PARAM_TERMS if term.casefold() in lowered]
    observation = (
        "script parece atualizar o bloco de status"
        if any(term in normalize_text(" ".join(terms)) for term in ("refresh", "lcd", "moni", "status"))
        else "script sem indicio direto de status dinamico"
    )
    return {
        "script": script_path,
        "termos_encontrados": _unique(terms),
        "funcoes_candidatas": _unique(functions),
        "endpoints_candidatos": endpoints,
        "metodos_candidatos": methods,
        "parametros_candidatos": _unique(params),
        "observacao": observation,
    }


def classify_dynamic_endpoint(path: str) -> tuple[bool, str | None]:
    normalized_path = normalize_text(path)
    for prefix in BLOCKED_DYNAMIC_PREFIXES:
        if normalized_path.startswith(normalize_text(prefix)):
            return False, "endpoint administrativo fora do escopo"
    if not any(term in normalized_path for term in SAFE_DYNAMIC_ENDPOINT_TERMS):
        return False, "endpoint fora do escopo de status dinamico"
    return True, None


def fetch_dynamic_relative_path(
    target: HtmlDiagnosticTarget,
    session,
    path: str,
    *,
    method: str = "GET",
    protocol: str | None = None,
    referer_path: str | None = None,
) -> DynamicHttpResult:
    config = target_to_config(target)
    concrete_protocol = protocol or ("https" if config.protocolo_preferencial == "https" else "http")
    try:
        url = build_html_url(target.ip or "", concrete_protocol, path, port=config.porta)
        headers = {}
        if referer_path:
            headers["Referer"] = build_html_url(
                target.ip or "",
                concrete_protocol,
                referer_path,
                port=config.porta,
            )
        auth = build_auth(config) if config.tipo_autenticacao in {"basic", "digest"} else None
        request_method = method.upper()
        if request_method == "POST":
            response = session.post(
                url,
                data={},
                headers=headers,
                auth=auth,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
        else:
            response = session.get(
                url,
                headers=headers,
                auth=auth,
                timeout=config.timeout_segundos,
                verify=config.validar_ssl,
            )
    except (RequestException, ValueError) as exc:
        return DynamicHttpResult(
            sucesso=False,
            status_code=None,
            conteudo=None,
            erro_codigo="falha_requisicao_dinamica",
            erro_detalhe_sanitizado=exc.__class__.__name__,
        )
    success = 200 <= response.status_code < 400
    return DynamicHttpResult(
        sucesso=success,
        status_code=response.status_code,
        conteudo=response.text if success else None,
        erro_codigo=None if success else "http_status_sem_sucesso",
        erro_detalhe_sanitizado=None if success else f"HTTP {response.status_code}",
    )


def _methods_for_endpoint(methods: list[str]) -> list[str]:
    if not methods:
        return ["GET"]
    return _unique([method.upper() for method in methods if method.upper() in {"GET", "POST"}], limit=2) or ["GET"]


def _candidate_call_summary(
    *,
    endpoint: str,
    method: str,
    response: DynamicHttpResult,
) -> dict[str, Any]:
    terms = detect_brother_l1632w_status_terms(response.conteudo or "")
    return {
        "endpoint": endpoint,
        "metodo": method,
        "status_http": response.status_code,
        "sucesso_http": response.sucesso,
        "texto_operacional_encontrado": bool(terms),
        "mensagens_detectadas": terms,
        "erro_codigo": response.erro_codigo,
    }


def diagnose_dynamic_status(
    target: HtmlDiagnosticTarget,
    *,
    status_fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
    resource_fetcher: Callable[..., DynamicHttpResult] = fetch_dynamic_relative_path,
) -> dict[str, Any]:
    if target.motivo_ignorado:
        return {
            "modelo": f"{target.fabricante} {target.modelo}",
            "maquina_sanitizada": sanitized_machine_label(target),
            "sucesso": False,
            "erro_codigo": target.motivo_ignorado,
        }
    if (normalize_text(target.fabricante), normalize_text(target.modelo)) != ("brother", "dcp-l1632w"):
        return {
            "modelo": f"{target.fabricante} {target.modelo}",
            "maquina_sanitizada": sanitized_machine_label(target),
            "sucesso": False,
            "erro_codigo": "diagnostico_dinamico_modelo_nao_suportado",
        }

    session = requests.Session()
    status_response = status_fetcher(
        target.ip,
        target_to_config(target),
        page_type="status",
        session=session,
    )
    initial_html = status_response.conteudo_html or ""
    script_refs = extract_script_references(initial_html)
    inline_scripts = script_refs.pop("_inline_raw")
    scripts_detected = script_refs["scripts_detectados"]
    inspected_scripts: list[dict[str, Any]] = []
    endpoint_methods: dict[str, set[str]] = {}

    for index, inline_script in enumerate(inline_scripts, start=1):
        analysis = analyze_dynamic_script(inline_script, script_path=f"inline_status_{index}")
        inspected_scripts.append(analysis)
        for endpoint in analysis["endpoints_candidatos"]:
            endpoint_methods.setdefault(endpoint, set()).update(_methods_for_endpoint(analysis["metodos_candidatos"]))

    protocol = status_response.protocolo_usado or (
        "https" if target.protocolo_preferencial == "https" else "http"
    )
    for script_path in scripts_detected:
        script_response = resource_fetcher(
            target,
            session,
            script_path,
            method="GET",
            protocol=protocol,
            referer_path=target.caminho_status,
        )
        analysis = analyze_dynamic_script(
            script_response.conteudo if script_response.sucesso else "",
            script_path=script_path,
        )
        analysis["status_http"] = script_response.status_code
        analysis["erro_codigo"] = script_response.erro_codigo
        inspected_scripts.append(analysis)
        for endpoint in analysis["endpoints_candidatos"]:
            endpoint_methods.setdefault(endpoint, set()).update(_methods_for_endpoint(analysis["metodos_candidatos"]))

    ignored_endpoints: list[dict[str, Any]] = []
    executed_calls: list[dict[str, Any]] = []
    confirmed: dict[str, Any] | None = None
    for endpoint, methods in sorted(endpoint_methods.items()):
        allowed, reason = classify_dynamic_endpoint(endpoint)
        if not allowed:
            ignored_endpoints.append(
                {
                    "endpoint": endpoint,
                    "ignorado": True,
                    "motivo": reason,
                }
            )
            continue
        for method in _methods_for_endpoint(sorted(methods)):
            response = resource_fetcher(
                target,
                session,
                endpoint,
                method=method,
                protocol=protocol,
                referer_path=target.caminho_status,
            )
            call = _candidate_call_summary(endpoint=endpoint, method=method, response=response)
            executed_calls.append(call)
            if call["texto_operacional_encontrado"] and confirmed is None:
                confirmed = {
                    "endpoint_dinamico_confirmado": True,
                    "endpoint": endpoint,
                    "metodo": method,
                    "mensagem_detectada": call["mensagens_detectadas"][0],
                    "status_http": call["status_http"],
                }

    cause = None
    if confirmed is None:
        if not endpoint_methods:
            cause = "scripts_sem_endpoint_candidato"
        elif executed_calls:
            if any(call.get("status_http") in {401, 403} for call in executed_calls):
                cause = "requer_cookie_ou_sessao_adicional"
            else:
                cause = "endpoint_candidato_sem_texto_operacional"
        else:
            cause = "nenhum_endpoint_dinamico_confirmado"

    result = {
        "modelo": f"{target.fabricante} {target.modelo}",
        "maquina_sanitizada": sanitized_machine_label(target),
        "caminho_status": target.caminho_status,
        "status_http_inicial": status_response.status_code,
        "auth_state": classify_brother_html_auth_state(initial_html),
        "moni_data_debug": build_brother_l1632w_moni_data_debug(initial_html),
        "scripts_detectados": scripts_detected,
        "scripts_inline_detectados": script_refs["scripts_inline"],
        "scripts_inspecionados": inspected_scripts,
        "endpoints_candidatos": sorted(endpoint_methods),
        "endpoints_ignorados": ignored_endpoints,
        "chamadas_candidatas_executadas": executed_calls,
        "endpoint_dinamico_confirmado": confirmed or {"endpoint_dinamico_confirmado": False},
        "texto_operacional_encontrado": bool(confirmed),
        "mensagem_operacional_encontrada": confirmed["mensagem_detectada"] if confirmed else None,
        "causa_sanitizada": cause,
        "pendencia_tecnica": (
            "endpoint dinamico identificado para futura integracao controlada"
            if confirmed
            else "descobrir chamada assincrona ou parametro adicional do painel Brother"
        ),
    }
    return sanitize_payload(result)


def build_dynamic_status_report(
    *,
    targets: list[HtmlDiagnosticTarget],
    confirmar: bool,
    status_fetcher: Callable[..., HtmlClientResponse] = fetch_html_page,
    resource_fetcher: Callable[..., DynamicHttpResult] = fetch_dynamic_relative_path,
    timestamp: datetime | None = None,
) -> dict[str, Any]:
    generated_at = timestamp or datetime.now()
    if not confirmar:
        return sanitize_payload(
            {
                "executado": False,
                "modo": "dry_run_dinamico",
                "gerado_em": generated_at.isoformat(timespec="seconds"),
                "mensagem": "Use --confirmar para consultar scripts e endpoints reais.",
                "alvos_planejados": [target.safe_dict() for target in targets],
            }
        )
    return sanitize_payload(
        {
            "executado": True,
            "modo": "confirmado_dinamico",
            "gerado_em": generated_at.isoformat(timespec="seconds"),
            "resultados": [
                diagnose_dynamic_status(
                    target,
                    status_fetcher=status_fetcher,
                    resource_fetcher=resource_fetcher,
                )
                for target in targets
            ],
        }
    )


def build_dynamic_status_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Diagnostico dinamico Brother DCP-L1632W",
        "",
        f"- Gerado em: {report.get('gerado_em')}",
        f"- Modo: {report.get('modo')}",
        "",
    ]
    for result in report.get("resultados", []):
        confirmed = result.get("endpoint_dinamico_confirmado") or {}
        lines.extend(
            [
                f"## {result.get('modelo')}",
                "",
                f"- Maquina: {result.get('maquina_sanitizada')}",
                f"- Caminho status: {result.get('caminho_status')}",
                f"- HTTP inicial: {result.get('status_http_inicial')}",
                f"- Scripts detectados: {', '.join(result.get('scripts_detectados') or []) or '-'}",
                f"- Endpoints candidatos: {', '.join(result.get('endpoints_candidatos') or []) or '-'}",
                f"- Endpoint confirmado: {confirmed.get('endpoint') or '-'}",
                f"- Mensagem encontrada: {result.get('mensagem_operacional_encontrada') or '-'}",
                f"- Causa sanitizada: {result.get('causa_sanitizada') or '-'}",
                "",
            ]
        )
    if not report.get("executado"):
        lines.append("Nenhuma requisicao HTTP real foi executada.")
        lines.append("")
    return "\n".join(lines)


def write_dynamic_status_reports(
    report: dict[str, Any],
    *,
    output_dir: Path = OUTPUT_DIR,
    write_json: bool = True,
    write_md: bool = True,
    timestamp: datetime | None = None,
) -> tuple[Path | None, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"{DYNAMIC_REPORT_PREFIX}_{stamp}.json"
    md_path = output_dir / f"{DYNAMIC_REPORT_PREFIX}_{stamp}.md"
    if write_json:
        json_path.write_text(
            json.dumps(sanitize_payload(report), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    else:
        json_path = None
    if write_md:
        md_path.write_text(
            build_dynamic_status_markdown(sanitize_payload(report)),
            encoding="utf-8",
        )
    else:
        md_path = None
    return json_path, md_path
