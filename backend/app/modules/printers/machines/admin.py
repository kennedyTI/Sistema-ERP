"""Django Admin do cadastro de maquinas."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel, PrinterModelAdminModel


@admin.register(PrinterModelAdminModel)
class PrinterModelAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = ("id", "manufacturer", "name", "type", "color_mode")
    list_display_links = ("id", "name")
    list_filter = ("manufacturer", "type", "color_mode")
    search_fields = ("manufacturer", "name", "type", "color_mode", "url_imagem")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("manufacturer", "name")


@admin.register(PrinterMachineAdminModel)
class PrinterMachineAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "ip_address", "sector", "is_active")
    list_display_links = ("id", "name")
    list_filter = ("is_active", "printer_model__manufacturer", "sector")
    search_fields = (
        "name",
        "ip_address",
        "printer_model__manufacturer",
        "printer_model__name",
        "sector",
        "cost_center",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name",)
