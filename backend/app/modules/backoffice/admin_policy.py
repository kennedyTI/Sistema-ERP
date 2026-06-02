"""
Politicas gerais de exposicao do Django Admin no portal.
"""


def can_access_django_admin(*, is_superuser: bool, group_names: list[str]) -> bool:
    return is_superuser or "Equipe T\u00e9cnica" in set(group_names)
