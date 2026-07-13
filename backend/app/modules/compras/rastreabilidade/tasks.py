"""Tasks Celery da rastreabilidade de compras."""

from __future__ import annotations

from backend.app.core.celery_app import celery_app
from backend.app.core.database import SessionLocal
from backend.app.core.redis_client import get_redis_client
from backend.app.modules.compras.rastreabilidade.workflow import (
    RastreabilidadeImportacaoEmAndamento,
    executar_importacao_com_lock,
)


@celery_app.task(name="compras_rastreabilidade_importar")
def compras_rastreabilidade_importar(
    *,
    execucao_id: int | None = None,
    origem: str = "agendada",
    criado_por: str | None = None,
    lock_token: str | None = None,
):
    redis_client = get_redis_client()
    db = SessionLocal()
    try:
        result = executar_importacao_com_lock(
            db,
            origem=origem,
            criado_por=criado_por,
            execucao_id=execucao_id,
            redis_client=redis_client,
            lock_token=lock_token,
        )
        return {
            "executada": True,
            "execucao_id": result.execucao_id,
            "total_registros": result.total_registros,
        }
    except RastreabilidadeImportacaoEmAndamento as exc:
        return {
            "executada": False,
            "motivo": "importacao_em_andamento",
            "execucao_id": exc.execution.id if exc.execution else None,
        }
    finally:
        db.close()
