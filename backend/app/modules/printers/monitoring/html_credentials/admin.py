"""Django Admin das credenciais de coleta HTML."""

from django import forms
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist

from backend.app.modules.audit.admin import AuditLogAdminMixin
from backend.app.modules.printers.monitoring.html_client.client import (
    validate_preferred_protocol,
    validate_relative_html_path,
    validate_timeout,
)
from backend.app.modules.printers.monitoring.html_client.exceptions import HtmlClientError
from backend.app.modules.printers.monitoring.html_credentials.crypto import (
    CredentialCryptoError,
    encrypt_password,
)
from backend.app.modules.printers.monitoring.html_credentials.django_models import (
    PrinterCollectionCredentialAdminModel,
)
from backend.app.modules.printers.monitoring.html_credentials.services import (
    build_html_access_description,
)


def credential_audit_snapshot(obj):
    data = {}
    for field in obj._meta.fields:
        if field.is_relation and hasattr(field, "attname"):
            value = getattr(obj, field.attname, None)
        else:
            value = getattr(obj, field.name, None)

        if field.name == "senha_criptografada":
            data[field.name] = "senha cadastrada" if value else "senha nao cadastrada"
        elif hasattr(value, "isoformat"):
            data[field.name] = value.isoformat()
        else:
            data[field.name] = value

    return data


class PrinterCollectionCredentialAdminForm(forms.ModelForm):
    senha = forms.CharField(
        label="SENHA",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Informe somente para criar ou alterar a senha. "
            "O valor real nunca e exibido."
        ),
    )

    class Meta:
        model = PrinterCollectionCredentialAdminModel
        fields = (
            "tipo_autenticacao",
            "modelo",
            "usuario",
            "caminho_status",
            "caminho_informacoes",
            "caminho_login",
            "timeout_segundos",
            "protocolo_preferencial",
            "validar_ssl",
            "ativo",
        )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("senha")
        self._encrypted_password = None

        if not self.instance.pk and not password:
            raise forms.ValidationError("Informe a senha da credencial.")

        if password:
            try:
                self._encrypted_password = encrypt_password(password)
            except CredentialCryptoError as exc:
                raise forms.ValidationError(str(exc)) from exc

        for field_name in ("caminho_status", "caminho_informacoes", "caminho_login"):
            try:
                cleaned_data[field_name] = validate_relative_html_path(
                    cleaned_data.get(field_name),
                    field_name=field_name,
                )
            except HtmlClientError as exc:
                self.add_error(field_name, exc.detail)

        try:
            validate_timeout(cleaned_data.get("timeout_segundos") or 5)
        except HtmlClientError as exc:
            self.add_error("timeout_segundos", exc.detail)

        try:
            validate_preferred_protocol(cleaned_data.get("protocolo_preferencial") or "auto")
        except HtmlClientError as exc:
            self.add_error("protocolo_preferencial", exc.detail)

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self._encrypted_password:
            instance.senha_criptografada = self._encrypted_password
        if commit:
            instance.save()
        return instance


@admin.register(PrinterCollectionCredentialAdminModel)
class PrinterCollectionCredentialAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    form = PrinterCollectionCredentialAdminForm
    list_display = (
        "modelo",
        "tipo_autenticacao",
        "protocolo_preferencial",
        "validar_ssl",
        "caminho_status",
        "caminho_informacoes",
        "ativo",
        "atualizado_em",
    )
    list_display_links = ("modelo",)
    list_filter = ("tipo_autenticacao", "protocolo_preferencial", "validar_ssl", "ativo", "modelo")
    search_fields = (
        "usuario",
        "modelo__manufacturer",
        "modelo__name",
        "caminho_status",
        "caminho_informacoes",
    )
    readonly_fields = ("descricao", "senha_mascarada", "criado_em", "atualizado_em")
    fields = (
        "descricao",
        "tipo_autenticacao",
        "modelo",
        "usuario",
        "senha",
        "senha_mascarada",
        "caminho_status",
        "caminho_informacoes",
        "caminho_login",
        "timeout_segundos",
        "protocolo_preferencial",
        "validar_ssl",
        "ativo",
        "criado_em",
        "atualizado_em",
    )
    ordering = ("modelo__manufacturer", "modelo__name")

    @admin.display(description="SENHA")
    def senha_mascarada(self, obj):
        if obj and obj.senha_criptografada:
            return "senha cadastrada"
        return "senha nao cadastrada"

    def _is_superuser(self, request) -> bool:
        user = getattr(request, "user", None)
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "is_staff", False)
            and getattr(user, "is_superuser", False)
        )

    def has_view_permission(self, request, obj=None):
        if self._is_superuser(request):
            return True

        user = getattr(request, "user", None)
        permission = f"{self.model._meta.app_label}.view_{self.model._meta.model_name}"
        return bool(
            user
            and getattr(user, "is_active", False)
            and getattr(user, "is_staff", False)
            and user.has_perm(permission)
        )

    def has_add_permission(self, request):
        return self._is_superuser(request)

    def has_change_permission(self, request, obj=None):
        return self._is_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not self._is_superuser(request) and "senha" in fields:
            fields.remove("senha")
        return fields

    def save_model(self, request, obj, form, change):
        if request is None:
            obj.descricao = build_html_access_description(
                printer_model=getattr(obj, "modelo", None),
                caminho_status=getattr(obj, "caminho_status", None),
            )
            return admin.ModelAdmin.save_model(self, request, obj, form, change)

        old_data = None
        action = "update" if change else "create"

        if change and getattr(obj, "pk", None):
            try:
                old_data = credential_audit_snapshot(self.model.objects.get(pk=obj.pk))
            except ObjectDoesNotExist:
                old_data = None

        obj.descricao = build_html_access_description(
            printer_model=getattr(obj, "modelo", None),
            caminho_status=getattr(obj, "caminho_status", None),
        )
        admin.ModelAdmin.save_model(self, request, obj, form, change)
        self._record_admin_audit(
            request=request,
            obj=obj,
            action=action,
            old_data=old_data,
            new_data=credential_audit_snapshot(obj),
        )
