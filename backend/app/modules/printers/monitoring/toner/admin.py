"""Django Admin consultivo do toner das impressoras."""

from django.contrib import admin

from backend.app.modules.audit.admin import ReadOnlyAdminMixin
from backend.app.modules.printers.monitoring.toner.django_models import (
    PrinterTonerHistoryAdminModel,
    PrinterTonerStatusAdminModel,
)


@admin.register(PrinterTonerStatusAdminModel)
class PrinterTonerStatusAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "cor",
        "percentual",
        "descricao_coletada",
        "sucesso",
        "coletado_em",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("cor", "sucesso", "origem_coleta", "metodo_coleta", "coletado_em")
    search_fields = ("maquina__name", "maquina__ip_address", "descricao_coletada")
    ordering = ("maquina__name", "cor", "indice_suprimento")


@admin.register(PrinterTonerHistoryAdminModel)
class PrinterTonerHistoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "cor",
        "percentual_anterior",
        "percentual_novo",
        "codigo_evento",
        "coletado_em",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("cor", "codigo_evento", "coletado_em")
    search_fields = ("maquina__name", "maquina__ip_address", "descricao_evento")
    ordering = ("-coletado_em", "-id")
