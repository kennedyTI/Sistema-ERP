"""
Servicos de sincronizacao dos grupos/permissoes oficiais.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from backend.app.modules.backoffice.groups import GROUPS, OLD_GROUP_RENAMES
from backend.app.modules.printers.django_models import PermissoesImpressoras
from backend.app.modules.printers.permissions import PERMISSOES_IMPRESSORAS


def merge_or_rename_group(old_name: str, new_name: str) -> str | None:
    old_group = Group.objects.filter(name=old_name).first()
    if old_group is None:
        return None

    new_group = Group.objects.filter(name=new_name).first()
    if new_group is None:
        old_group.name = new_name
        old_group.save(update_fields=["name"])
        return f"Grupo {old_name!r} renomeado para {new_name!r}."

    new_group.permissions.add(*old_group.permissions.all())
    for user in old_group.user_set.all():
        user.groups.add(new_group)
    old_group.delete()
    return f"Grupo legado {old_name!r} mesclado em {new_name!r}."


def get_permissions(app_label: str, rules):
    if rules == "all":
        return Permission.objects.filter(content_type__app_label=app_label)

    return Permission.objects.filter(
        content_type__app_label=app_label,
        codename__in=rules,
    )


def ensure_printer_permissions() -> None:
    content_type = ContentType.objects.get_for_model(
        PermissoesImpressoras,
        for_concrete_model=False,
    )
    for codename, name in PERMISSOES_IMPRESSORAS.items():
        Permission.objects.update_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )


def sync_official_groups() -> list[str]:
    messages: list[str] = []
    ensure_printer_permissions()

    for old_name, new_name in OLD_GROUP_RENAMES:
        message = merge_or_rename_group(old_name, new_name)
        if message:
            messages.append(message)

    for group_name, config in GROUPS.items():
        group, created = Group.objects.get_or_create(name=group_name)
        group.permissions.clear()

        total_permissions = 0
        for app_label, rules in config["permissions"].items():
            permissions = list(get_permissions(app_label, rules))
            group.permissions.add(*permissions)
            total_permissions += len(permissions)

        status = "criado" if created else "atualizado"
        messages.append(f"Grupo {group_name!r} {status} com {total_permissions} permissao(oes).")

    messages.append("Grupos oficiais do Django Admin criados/atualizados com sucesso.")
    return messages
