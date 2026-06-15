"""Django Admin do status operacional das impressoras."""

from django.contrib import admin

from backend.app.modules.audit.admin import ReadOnlyAdminMixin
from backend.app.modules.printers.status.django_models import (
    PrinterLogAdminModel,
    PrinterStatusAdminModel,
    PrinterStatusHistoryAdminModel,
)


# ---------------------------------------------------------------------
# 📌 STATUS OPERACIONAL SOMENTE PARA CONSULTA
# ---------------------------------------------------------------------
# O mixin bloqueia inclusão, alteração e exclusão inclusive para superusuários.
# Escritas futuras devem ocorrer apenas pelo fluxo operacional auditável.
@admin.register(PrinterStatusAdminModel)
class PrinterStatusAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "status_operacional",
        "nivel_alerta",
        "metodo_confirmacao",
        "ultima_verificacao_em",
        "origem",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("status_operacional", "nivel_alerta", "metodo_confirmacao", "origem")
    search_fields = ("maquina__name", "maquina__ip_address", "mensagem_alerta")
    ordering = ("maquina__name",)


@admin.register(PrinterStatusHistoryAdminModel)
class PrinterStatusHistoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "status_anterior",
        "status_novo",
        "metodo_confirmacao",
        "codigo_evento",
        "verificado_em",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("status_novo", "metodo_confirmacao", "verificado_em")
    search_fields = (
        "maquina__name",
        "maquina__ip_address",
        "codigo_evento",
        "descricao_evento",
    )
    ordering = ("-verificado_em", "-id")


@admin.register(PrinterLogAdminModel)
class PrinterLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "maquina", "tipo_evento", "status_novo", "alerta_novo", "verificado_em")
    list_display_links = ("id", "maquina")
    list_filter = ("tipo_evento", "status_novo", "alerta_novo", "origem")
    search_fields = ("maquina__name", "maquina__ip_address", "mensagem")
    ordering = ("-criado_em",)
