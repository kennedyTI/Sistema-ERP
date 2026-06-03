"""Services iniciais de maquinas."""

from backend.app.modules.printers.machines.models import PrinterMachine


def list_machines() -> list[PrinterMachine]:
    """Retorna o inventario inicial, vazio ate a etapa de persistencia."""
    return []
