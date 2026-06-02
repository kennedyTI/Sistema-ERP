"""
Django Admin da base v2 limpa.
"""

from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist

from backend.app.modules.audit.models import AuditLog, Log

admin.site.site_header = "Portal industria"
admin.site.site_title = "Admin"
admin.site.index_title = "Backoffice"


def _to_audit_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def _model_snapshot(obj):
    data = {}
    for field in obj._meta.fields:
        if field.is_relation and hasattr(field, "attname"):
            value = getattr(obj, field.attname, None)
        else:
            value = getattr(obj, field.name, None)
        data[field.name] = _to_audit_value(value)
    return data


class AuditLogAdminMixin:
    audit_source = "django_admin"

    def _get_changed_by(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return user.get_username()
        return "django_admin"

    def _record_admin_audit(self, request, obj, action, old_data=None, new_data=None):
        if request is None:
            return

        try:
            AuditLog.objects.create(
                table_name=obj._meta.db_table,
                record_id=getattr(obj, "pk", None),
                action=action,
                old_data=old_data,
                new_data=new_data,
                changed_by=self._get_changed_by(request),
                source=self.audit_source,
            )
        except Exception as exc:  # pragma: no cover
            self.message_user(
                request,
                f"Nao foi possivel registrar audit_log: {exc}",
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        if request is None:
            return super().save_model(request, obj, form, change)

        old_data = None
        action = "update" if change else "create"

        if change and getattr(obj, "pk", None):
            try:
                old_data = _model_snapshot(self.model.objects.get(pk=obj.pk))
            except ObjectDoesNotExist:
                old_data = None

        super().save_model(request, obj, form, change)
        self._record_admin_audit(
            request=request,
            obj=obj,
            action=action,
            old_data=old_data,
            new_data=_model_snapshot(obj),
        )

    def delete_model(self, request, obj):
        if request is None:
            return super().delete_model(request, obj)

        old_data = _model_snapshot(obj)
        super().delete_model(request, obj)
        self._record_admin_audit(
            request=request,
            obj=obj,
            action="delete",
            old_data=old_data,
            new_data=None,
        )


class ReadOnlyAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Log)
class LogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "tipo",
        "message",
        "valor_anterior",
        "valor_novo",
        "created_at",
    )
    list_filter = ("tipo",)
    search_fields = ("message", "valor_anterior", "valor_novo")
    ordering = ("-created_at",)


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("id", "table_name", "record_id", "action", "source", "changed_by", "created_at")
    list_filter = ("table_name", "action", "source")
    search_fields = ("table_name", "changed_by")
    ordering = ("-created_at",)
