"""Django Admin dos alertas persistidos de impressoras."""

from django.contrib import admin

from backend.app.modules.audit.admin import ReadOnlyAdminMixin
from backend.app.modules.printers.monitoring.alerts.django_models import (
    PrinterAlertHistoryAdminModel,
    PrinterCurrentAlertAdminModel,
)


@admin.register(PrinterCurrentAlertAdminModel)
class PrinterCurrentAlertAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "regra_alerta",
        "origem_coleta",
        "metodo_confirmacao",
        "metodo_coleta",
        "verificado_em",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("origem_coleta", "metodo_confirmacao", "metodo_coleta", "verificado_em")
    search_fields = (
        "maquina__name",
        "maquina__ip_address",
        "regra_alerta__codigo",
        "mensagem_original",
        "chave_alerta",
    )
    ordering = ("maquina__name", "chave_alerta")


@admin.register(PrinterAlertHistoryAdminModel)
class PrinterAlertHistoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "codigo_alerta",
        "codigo_evento",
        "classificacao_anterior",
        "classificacao_nova",
        "verificado_em",
    )
    list_display_links = ("id", "maquina")
    list_filter = (
        "codigo_evento",
        "classificacao_nova",
        "origem_coleta",
        "metodo_confirmacao",
        "verificado_em",
    )
    search_fields = (
        "maquina__name",
        "maquina__ip_address",
        "codigo_alerta",
        "mensagem_original",
        "chave_alerta",
    )
    ordering = ("-verificado_em", "-id")
