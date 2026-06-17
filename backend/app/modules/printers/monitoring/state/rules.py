"""Rules Engine para normalizacao de alertas de impressoras."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from backend.app.modules.printers.monitoring.state.models import PrinterAlertRule


ALLOWED_RULE_TYPES = {"contains", "equals", "regex"}
ALLOWED_SEVERITIES = {"green", "low", "medium", "high", "unknown"}


# ---------------------------------------------------------------------
# 📌 NORMALIZACAO COMPATIVEL COM A V1
# ---------------------------------------------------------------------
def normalize_text(value: str | None) -> str:
    """Remove acentos, ignora caixa e uniformiza espacos."""
    if value is None:
        return ""

    decomposed = unicodedata.normalize("NFKD", str(value))
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().strip().split())


def match_rule(rule_type: str, pattern: str, normalized_message: str) -> bool:
    """Executa contains, equals ou regex sem propagar padroes invalidos."""
    normalized_rule_type = normalize_text(rule_type)
    if normalized_rule_type not in ALLOWED_RULE_TYPES or not pattern:
        return False

    if normalized_rule_type == "contains":
        keywords = (
            normalize_text(keyword)
            for keyword in pattern.split(",")
            if keyword.strip()
        )
        return any(keyword in normalized_message for keyword in keywords)

    if normalized_rule_type == "equals":
        return normalized_message == normalize_text(pattern)

    regex_patterns = [pattern]
    if "\\\\" in pattern:
        regex_patterns.append(pattern.replace("\\\\", "\\"))

    for regex_pattern in regex_patterns:
        try:
            normalized_pattern = normalize_text(regex_pattern)
            if re.search(normalized_pattern, normalized_message) is not None:
                return True
        except re.error:
            continue
    return False


def load_active_alert_rules(db: Session) -> list[PrinterAlertRule]:
    """Carrega regras ativas na mesma ordem deterministica da classificacao."""
    return (
        db.query(PrinterAlertRule)
        .filter(PrinterAlertRule.ativo.is_(True))
        .order_by(PrinterAlertRule.prioridade.asc(), PrinterAlertRule.codigo.asc())
        .all()
    )


def _safe_severity(value: str | None) -> str:
    return value if value in ALLOWED_SEVERITIES else "medium"


def _result_from_rule(
    rule: PrinterAlertRule,
    original_message: str | None,
    *,
    recognized: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "codigo": rule.codigo,
        "descricao": rule.descricao,
        "severidade": _safe_severity(rule.severidade),
        "mensagem_original": original_message,
        "reconhecido": recognized,
    }
    if recognized:
        result.update(
            {
                "tipo_regra": rule.tipo_regra,
                "padrao": rule.padrao,
                "prioridade": rule.prioridade,
            }
        )
    return result


# ---------------------------------------------------------------------
# 📌 CLASSIFICACAO DETERMINISTICA
# ---------------------------------------------------------------------
def classify_alert(
    raw_message: str | None,
    rules: Iterable[PrinterAlertRule],
) -> dict[str, Any]:
    """Classifica uma mensagem preservando o texto original no resultado."""
    original_message = raw_message
    normalized_message = normalize_text(raw_message)
    active_rules = [rule for rule in rules if rule.ativo]
    active_rules.sort(key=lambda rule: (rule.prioridade, normalize_text(rule.codigo)))

    if not normalized_message:
        ok_rule = next((rule for rule in active_rules if rule.codigo == "ok"), None)
        if ok_rule is not None:
            return _result_from_rule(ok_rule, original_message, recognized=True)

    for rule in active_rules:
        if rule.codigo == "unknown":
            continue
        if match_rule(rule.tipo_regra, rule.padrao, normalized_message):
            return _result_from_rule(rule, original_message, recognized=True)

    fallback = next(
        (rule for rule in active_rules if rule.codigo == "unknown"),
        None,
    )
    if fallback is None:
        fallback = PrinterAlertRule(
            codigo="unknown",
            descricao="Alerta nao reconhecido",
            severidade="medium",
            tipo_regra="contains",
            padrao="",
            prioridade=999,
            ativo=True,
        )
    return _result_from_rule(fallback, original_message, recognized=False)


def classify_alert_from_database(
    db: Session,
    raw_message: str | None,
) -> dict[str, Any]:
    """Atalho interno que usa as regras ativas persistidas."""
    return classify_alert(raw_message, load_active_alert_rules(db))
