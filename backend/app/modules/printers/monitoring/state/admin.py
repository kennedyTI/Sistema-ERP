"""Django Admin das regras de alertas de impressoras."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.monitoring.state.django_models import (
    PrinterAlertRuleAdminModel,
)


# ---------------------------------------------------------------------
# 📌 CONFIGURACAO ADMINISTRAVEL DA RULES ENGINE
# ---------------------------------------------------------------------
# As permissoes padrao do Django limitam a escrita aos grupos administrativos.
# Operadores do portal nao recebem acesso a este aplicativo.
@admin.register(PrinterAlertRuleAdminModel)
class PrinterAlertRuleAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "codigo",
        "descricao",
        "severidade",
        "tipo_regra",
        "prioridade",
        "ativo",
    )
    list_display_links = ("id", "codigo")
    list_filter = ("severidade", "tipo_regra", "ativo")
    search_fields = ("codigo", "descricao", "padrao")
    readonly_fields = ("criado_em", "atualizado_em")
    ordering = ("prioridade", "codigo")
