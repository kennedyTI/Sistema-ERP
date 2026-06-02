"""
Helpers de enums mantidos para futuros modulos.
"""


def enum_values(enum_class) -> tuple[str, ...]:
    return tuple(item.value for item in enum_class)
