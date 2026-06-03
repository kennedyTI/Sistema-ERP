"""Schemas do dashboard inicial de Impressoras."""

from typing import Literal

from pydantic import BaseModel


class DashboardStatus(BaseModel):
    module: Literal["printers_dashboard"] = "printers_dashboard"
    status: Literal["development"] = "development"
    message: str
