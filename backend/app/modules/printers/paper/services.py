"""Services iniciais do submodulo Papel."""

from backend.app.modules.printers.paper.schemas import PaperStatus


def get_paper_status() -> PaperStatus:
    return PaperStatus(message="Funcionalidade sera implementada nas proximas etapas.")
