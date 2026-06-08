"""Django Admin do cadastro de maquinas."""

from django.contrib import admin

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.machines.django_models import PrinterMachineAdminModel, PrinterModelAdminModel


@admin.register(PrinterModelAdminModel)
class PrinterModelAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = ("id", "manufacturer", "name", "type", "color_mode")
    list_filter = ("manufacturer", "type", "color_mode")
    search_fields = ("manufacturer", "name", "type", "color_mode")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("manufacturer", "name")


@admin.register(PrinterMachineAdminModel)
class PrinterMachineAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = ("id", "name", "ip_address", "manufacturer_display", "model_display", "sector", "is_active")
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

    @admin.display(ordering="printer_model__manufacturer", description="Fabricante")
    def manufacturer_display(self, obj):
        return obj.printer_model.manufacturer if obj.printer_model else "-"

    @admin.display(ordering="printer_model__name", description="Modelo")
    def model_display(self, obj):
        return obj.printer_model.name if obj.printer_model else "-"
