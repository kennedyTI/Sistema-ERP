"""Aplicacao Celery do Sistema ERP."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab


celery_app = Celery(
    "sistema_erp",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    include=[
        "backend.app.modules.compras.rastreabilidade.tasks",
        "backend.app.modules.printers.monitoring.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=os.getenv("TIME_ZONE", "America/Sao_Paulo"),
    enable_utc=False,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=int(os.getenv("CELERY_RESULT_EXPIRES_SECONDS", "3600")),
    beat_schedule={
        "printers-connectivity-every-60-seconds": {
            "task": "printers_connectivity_all",
            "schedule": float(os.getenv("PRINTER_CONNECTIVITY_INTERVAL_SECONDS", "60")),
        },
        "printers-alerts-every-5-minutes": {
            "task": "printers_alerts_all",
            "schedule": float(os.getenv("PRINTER_ALERTS_INTERVAL_SECONDS", "300")),
        },
        "printers-toner-every-60-minutes": {
            "task": "printers_toner_all",
            "schedule": float(os.getenv("PRINTER_TONER_INTERVAL_SECONDS", "3600")),
        },
        "compras-rastreabilidade-00-06-12-18": {
            "task": "compras_rastreabilidade_importar",
            "schedule": crontab(minute=0, hour="0,6,12,18"),
            "kwargs": {"origem": "agendada"},
        },
    },
)
