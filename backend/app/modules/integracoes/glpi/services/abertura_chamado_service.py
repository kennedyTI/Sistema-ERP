"""Abertura idempotente de chamados no GLPI."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.timezone import now_sao_paulo
from backend.app.modules.integracoes.glpi.clients.glpi_client import GlpiClient
from backend.app.modules.integracoes.glpi.config import GlpiSettings, get_glpi_settings
from backend.app.modules.integracoes.glpi.exceptions import GlpiIntegrationError
from backend.app.modules.integracoes.glpi.models.glpi_chamados import GlpiChamado
from backend.app.modules.integracoes.glpi.schemas.abertura_chamado_schema import (
    AbrirChamadoGlpiRequest,
    ResultadoAberturaGlpi,
)


NON_RETRYABLE_ACTIVE_STATUSES = {"pendente", "aberto"}


def _existing_record(db: Session, deduplication_hash: str) -> GlpiChamado | None:
    return (
        db.query(GlpiChamado)
        .filter(
            GlpiChamado.hash_deduplicacao == deduplication_hash,
            GlpiChamado.encerrado_em.is_(None),
        )
        .order_by(GlpiChamado.id.desc())
        .first()
    )


def _ticket_input(
    request: AbrirChamadoGlpiRequest,
    settings: GlpiSettings,
) -> dict[str, Any]:
    category_id = request.categoria_id or settings.printer_supply_category_id
    location_id = request.localizacao_id or settings.location_cariacica_id
    payload: dict[str, Any] = {
        "name": request.titulo,
        "content": request.descricao,
        "entities_id": settings.entity_id,
        "type": settings.default_type,
        "itilcategories_id": category_id,
        "status": settings.default_status,
        "requesttypes_id": settings.request_type_id,
        "impact": settings.default_impact,
        "priority": settings.default_priority,
        "urgency": request.urgency or settings.default_urgency,
        "locations_id": location_id,
    }
    requester_user_id = request.requester_user_id or settings.requester_user_id
    assign_user_id = request.assign_user_id or settings.assign_user_id
    assign_group_id = request.assign_group_id or settings.assign_group_id
    if requester_user_id is not None:
        payload["_users_id_requester"] = requester_user_id
    if assign_user_id is not None:
        payload["_users_id_assign"] = assign_user_id
    if assign_group_id is not None:
        payload["_groups_id_assign"] = assign_group_id
    return {key: value for key, value in payload.items() if value is not None}


def _missing_routing_fields(
    request: AbrirChamadoGlpiRequest,
    settings: GlpiSettings,
) -> list[str]:
    fields = {
        "GLPI_ENTITY_ID": settings.entity_id,
        "GLPI_TICKET_CATEGORY_IMPRESSORAS_INSUMO_ID": request.categoria_id
        or settings.printer_supply_category_id,
        "GLPI_LOCATION_CARIACICA_ID": request.localizacao_id
        or settings.location_cariacica_id,
        "GLPI_REQUEST_TYPE_ID": settings.request_type_id,
        "GLPI_REQUESTER_USER_ID": request.requester_user_id
        or settings.requester_user_id,
        "GLPI_ASSIGN_USER_ID": request.assign_user_id or settings.assign_user_id,
        "GLPI_ASSIGN_GROUP_ID": request.assign_group_id or settings.assign_group_id,
    }
    return [name for name, value in fields.items() if value is None]


def _record_for_request(
    db: Session,
    request: AbrirChamadoGlpiRequest,
    settings: GlpiSettings,
) -> tuple[GlpiChamado, bool]:
    existing = _existing_record(db, request.hash_deduplicacao)
    if existing is not None:
        return existing, False
    row = GlpiChamado(
        origem_modulo=request.origem_modulo,
        origem_entidade=request.origem_entidade,
        origem_entidade_id=request.origem_entidade_id,
        tipo_evento=request.tipo_evento,
        titulo_chamado=request.titulo,
        descricao_chamado=request.descricao,
        glpi_entities_id=settings.entity_id,
        glpi_itilcategories_id=request.categoria_id
        or settings.printer_supply_category_id,
        glpi_locations_id=request.localizacao_id or settings.location_cariacica_id,
        glpi_requesttypes_id=settings.request_type_id,
        glpi_status=settings.default_status,
        status_integracao="pendente",
        hash_deduplicacao=request.hash_deduplicacao,
    )
    db.add(row)
    db.flush()
    return row, True


def abrir_chamado_glpi(
    db: Session,
    request: AbrirChamadoGlpiRequest,
    *,
    settings: GlpiSettings | None = None,
    client: GlpiClient | None = None,
) -> ResultadoAberturaGlpi:
    config = settings or get_glpi_settings()
    try:
        row, created = _record_for_request(db, request, config)
    except IntegrityError:
        db.rollback()
        row = _existing_record(db, request.hash_deduplicacao)
        if row is None:
            raise
        return ResultadoAberturaGlpi(
            registro_id=row.id,
            status_integracao=row.status_integracao,
            glpi_ticket_id=row.glpi_ticket_id,
            duplicado=True,
        )
    if not created and row.status_integracao in NON_RETRYABLE_ACTIVE_STATUSES:
        return ResultadoAberturaGlpi(
            registro_id=row.id,
            status_integracao=row.status_integracao,
            glpi_ticket_id=row.glpi_ticket_id,
            duplicado=True,
        )

    missing_routing = _missing_routing_fields(request, config)
    if missing_routing:
        row.status_integracao = "bloqueado_dados_incompletos"
        row.ultimo_erro = (
            "Configuracao GLPI incompleta para abertura exata: "
            + ", ".join(missing_routing)
            + "."
        )
        row.atualizado_em = now_sao_paulo()
        db.commit()
        return ResultadoAberturaGlpi(
            registro_id=row.id,
            status_integracao=row.status_integracao,
            erro=row.ultimo_erro,
        )

    payload = _ticket_input(request, config)
    now = now_sao_paulo()
    row.titulo_chamado = request.titulo
    row.descricao_chamado = request.descricao
    row.payload_enviado = {"input": payload}
    row.status_integracao = "pendente"
    row.ultimo_erro = None
    row.ultima_tentativa_em = now
    row.tentativas = int(row.tentativas or 0) + 1
    db.commit()

    try:
        glpi_client = client or GlpiClient(config)
        response = glpi_client.open_ticket(payload)
        ticket_id = response.get("id") if isinstance(response, dict) else None
        if not isinstance(ticket_id, int):
            raise GlpiIntegrationError("GLPI nao retornou o identificador do chamado.")
    except GlpiIntegrationError as exc:
        row.status_integracao = "erro"
        row.ultimo_erro = str(exc)
        row.atualizado_em = now_sao_paulo()
        db.commit()
        return ResultadoAberturaGlpi(
            registro_id=row.id,
            status_integracao=row.status_integracao,
            erro=row.ultimo_erro,
        )

    row.glpi_ticket_id = ticket_id
    row.resposta_glpi = response
    row.glpi_status = config.default_status
    row.status_integracao = "aberto"
    row.aberto_em = now_sao_paulo()
    row.atualizado_em = row.aberto_em
    db.commit()
    return ResultadoAberturaGlpi(
        registro_id=row.id,
        status_integracao=row.status_integracao,
        glpi_ticket_id=row.glpi_ticket_id,
    )


def registrar_bloqueio_glpi(
    db: Session,
    request: AbrirChamadoGlpiRequest,
    *,
    erro: str,
    settings: GlpiSettings | None = None,
) -> ResultadoAberturaGlpi:
    config = settings or get_glpi_settings()
    row, _created = _record_for_request(db, request, config)
    if row.status_integracao == "aberto":
        return ResultadoAberturaGlpi(
            registro_id=row.id,
            status_integracao=row.status_integracao,
            glpi_ticket_id=row.glpi_ticket_id,
            duplicado=True,
        )
    row.status_integracao = "bloqueado_dados_incompletos"
    row.ultimo_erro = erro
    row.payload_enviado = None
    row.atualizado_em = now_sao_paulo()
    db.commit()
    return ResultadoAberturaGlpi(
        registro_id=row.id,
        status_integracao=row.status_integracao,
        erro=erro,
    )
