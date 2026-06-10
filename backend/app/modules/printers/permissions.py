"""Codenames oficiais das permissoes funcionais de Impressoras."""

PERMISSOES_IMPRESSORAS = {
    "ver_dashboard": "Pode visualizar o dashboard de impressoras",
    "ver_status": "Pode visualizar o status operacional de impressoras",
    "ver_maquinas": "Pode visualizar as maquinas cadastradas",
    "criar_maquinas": "Pode criar maquinas",
    "editar_maquinas": "Pode editar maquinas",
    "alternar_status_maquinas": "Pode ativar ou inativar maquinas",
    "ver_papel": "Pode visualizar o modulo de papel",
}

PERMISSOES_EQUIPE_TECNICA = set(PERMISSOES_IMPRESSORAS)
PERMISSOES_GESTOR = set(PERMISSOES_IMPRESSORAS)
PERMISSOES_OPERADOR = {
    "ver_dashboard",
    "ver_status",
}


def nome_permissao(codename: str) -> str:
    return f"impressoras.{codename}"
