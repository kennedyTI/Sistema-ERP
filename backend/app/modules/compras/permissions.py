"""Codenames oficiais das permissoes funcionais de Compras."""

PERMISSOES_COMPRAS = {
    "ver_rastreabilidade": "Pode visualizar rastreabilidade de compras",
    "atualizar_rastreabilidade": "Pode atualizar rastreabilidade de compras",
}

PERMISSOES_COMPRAS_EQUIPE_TECNICA = set(PERMISSOES_COMPRAS)
PERMISSOES_COMPRAS_GESTOR = set(PERMISSOES_COMPRAS)
PERMISSOES_COMPRAS_OPERADOR: set[str] = set()


def nome_permissao(codename: str) -> str:
    return f"compras.{codename}"
