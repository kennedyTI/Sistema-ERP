"""
Grupos oficiais do Portal v2.
"""

from backend.app.modules.auth.permissions import (
    GROUP_EQUIPE_TECNICA,
    GROUP_GESTOR,
    GROUP_INTEGRACAO_PROTHEUS,
    GROUP_OPERADOR,
)
from backend.app.modules.backoffice.permissions import BACKOFFICE_READONLY_PERMISSIONS
from backend.app.modules.printers.permissions import (
    PERMISSOES_EQUIPE_TECNICA,
    PERMISSOES_GESTOR,
    PERMISSOES_OPERADOR,
)

GROUPS = {
    GROUP_EQUIPE_TECNICA: {
        "description": "Acessa Impressoras, Papel e o Django Admin.",
        "permissions": {
            "audit": BACKOFFICE_READONLY_PERMISSIONS,
            "impressoras": PERMISSOES_EQUIPE_TECNICA,
            "printer_machines": "all",
            "printer_status": {
                "view_printerstatusadminmodel",
                "view_printerstatushistoryadminmodel",
            },
        },
    },
    GROUP_GESTOR: {
        "description": "Acessa Impressoras, incluindo Papel; nao ve Admin.",
        "permissions": {
            "impressoras": PERMISSOES_GESTOR,
        },
    },
    GROUP_OPERADOR: {
        "description": "Acessa Dashboard e Status; nao ve Maquinas, Papel ou Admin.",
        "permissions": {
            "impressoras": PERMISSOES_OPERADOR,
        },
    },
    GROUP_INTEGRACAO_PROTHEUS: {
        "description": "Grupo reservado para integracoes; nao acessa portal visual.",
        "permissions": {},
    },
}

OLD_GROUP_RENAMES = (
    ("Administrador", GROUP_EQUIPE_TECNICA),
    ("T\u00e9cnico", GROUP_OPERADOR),
)
