"""Django Admin do cadastro de maquinas."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel


@admin.register(PrinterMachineAdminModel)
class PrinterMachineAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "ip_address", "manufacturer", "model", "sector", "is_active")
    list_filter = ("is_active", "manufacturer", "sector")
    search_fields = ("name", "ip_address", "manufacturer", "model", "sector", "cost_center")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
