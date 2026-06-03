"""Services iniciais do dashboard de Impressoras."""

from backend.app.modules.printers.dashboard.schemas import DashboardStatus


def get_dashboard_status() -> DashboardStatus:
    return DashboardStatus(message="Funcionalidade sera implementada nas proximas etapas.")
