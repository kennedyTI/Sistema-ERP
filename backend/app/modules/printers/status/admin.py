"""Django Admin do status operacional das impressoras."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin, ReadOnlyAdminMixin
from backend.app.modules.printers.status.django_models import PrinterLogAdminModel, PrinterStatusAdminModel


@admin.register(PrinterStatusAdminModel)
class PrinterStatusAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "maquina",
        "status_operacional",
        "nivel_alerta",
        "ultima_verificacao_em",
        "origem",
    )
    list_display_links = ("id", "maquina")
    list_filter = ("status_operacional", "nivel_alerta", "origem")
    search_fields = ("maquina__name", "maquina__ip_address", "mensagem_alerta")
    readonly_fields = ("criado_em", "atualizado_em")
    ordering = ("maquina__name",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PrinterLogAdminModel)
class PrinterLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "maquina", "tipo_evento", "status_novo", "alerta_novo", "verificado_em")
    list_display_links = ("id", "maquina")
    list_filter = ("tipo_evento", "status_novo", "alerta_novo", "origem")
    search_fields = ("maquina__name", "maquina__ip_address", "mensagem")
    ordering = ("-criado_em",)
