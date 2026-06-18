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
        "regra_alerta_resumida",
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

    @admin.display(description="REGRA", ordering="regra_alerta_id")
    def regra_alerta_resumida(self, obj):
        if not obj or not obj.regra_alerta_id:
            return "-"
        code = getattr(getattr(obj, "regra_alerta", None), "codigo", None) or "-"
        return f"#{obj.regra_alerta_id} - {code}"


@admin.register(PrinterAlertHistoryAdminModel)
class PrinterAlertHistoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "regra_alerta_resumida",
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

    @admin.display(description="REGRA", ordering="regra_alerta_id")
    def regra_alerta_resumida(self, obj):
        if not obj or not obj.regra_alerta_id:
            return "-"
        return f"#{obj.regra_alerta_id} - {obj.codigo_alerta}"
