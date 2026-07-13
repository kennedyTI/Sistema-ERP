"""Orquestracao de importacao com lock e execucao assincrona."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from redis import Redis
from sqlalchemy.orm import Session

from backend.app.modules.compras.rastreabilidade.importer import (
    ImportacaoRastreabilidadeResultado,
    importar_rastreabilidade_compras,
)
from backend.app.modules.compras.rastreabilidade.models import (
    ComprasRastreabilidadeExecucao,
)
from backend.app.modules.compras.rastreabilidade.selectors import (
    buscar_execucao_em_andamento,
    criar_execucao_em_andamento,
)
from backend.app.modules.printers.monitoring.locks import acquire_lock, release_lock


IMPORT_LOCK_KEY = "compras:rastreabilidade:importacao"
IMPORT_LOCK_TTL_SECONDS = 3 * 60 * 60


class RastreabilidadeImportacaoEmAndamento(Exception):
    def __init__(self, execution: ComprasRastreabilidadeExecucao | None = None) -> None:
        self.execution = execution
        super().__init__("Ja existe uma atualizacao de rastreabilidade em andamento.")


@dataclass(frozen=True)
class AtualizacaoSolicitada:
    status: str
    mensagem: str
    execucao_id: int | None = None


def executar_importacao_com_lock(
    db: Session,
    *,
    origem: str,
    criado_por: str | None = None,
    execucao_id: int | None = None,
    redis_client: Redis,
    lock_token: str | None = None,
) -> ImportacaoRastreabilidadeResultado:
    token = lock_token
    lock_adquirido_aqui = False
    if token is None:
        token = acquire_lock(
            IMPORT_LOCK_KEY,
            IMPORT_LOCK_TTL_SECONDS,
            client=redis_client,
        )
        lock_adquirido_aqui = token is not None
        if token is None:
            raise RastreabilidadeImportacaoEmAndamento(buscar_execucao_em_andamento(db))

    try:
        return importar_rastreabilidade_compras(
            db,
            origem=origem,
            criado_por=criado_por,
            execucao_id=execucao_id,
        )
    finally:
        if token is not None and (lock_adquirido_aqui or lock_token is not None):
            release_lock(IMPORT_LOCK_KEY, token, client=redis_client)


def solicitar_atualizacao_manual(
    db: Session,
    *,
    criado_por: str,
    redis_client: Redis,
    task_sender: Callable[..., Any] | None = None,
) -> AtualizacaoSolicitada:
    running = buscar_execucao_em_andamento(db)
    if running is not None:
        return AtualizacaoSolicitada(
            status="em_andamento",
            mensagem="Ja existe uma atualizacao de rastreabilidade em andamento.",
            execucao_id=running.id,
        )

    token = acquire_lock(
        IMPORT_LOCK_KEY,
        IMPORT_LOCK_TTL_SECONDS,
        client=redis_client,
    )
    if token is None:
        return AtualizacaoSolicitada(
            status="em_andamento",
            mensagem="Ja existe uma atualizacao de rastreabilidade em andamento.",
            execucao_id=None,
        )

    execution = criar_execucao_em_andamento(
        db,
        origem="manual",
        criado_por=criado_por,
    )
    try:
        if task_sender is None:
            from backend.app.modules.compras.rastreabilidade.tasks import (
                compras_rastreabilidade_importar,
            )

            task_sender = compras_rastreabilidade_importar.apply_async
        task_sender(
            kwargs={
                "execucao_id": execution.id,
                "origem": "manual",
                "criado_por": criado_por,
                "lock_token": token,
            }
        )
    except Exception:
        release_lock(IMPORT_LOCK_KEY, token, client=redis_client)
        execution.status = "erro"
        execution.total_com_erro = 1
        execution.mensagem_erro_sanitizada = (
            "Falha sanitizada ao enfileirar atualizacao de rastreabilidade."
        )
        db.commit()
        raise

    return AtualizacaoSolicitada(
        status="iniciada",
        mensagem="Atualizacao da rastreabilidade iniciada.",
        execucao_id=execution.id,
    )
