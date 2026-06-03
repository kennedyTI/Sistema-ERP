"""Schemas do submodulo Papel."""

from typing import Literal

from pydantic import BaseModel


class PaperStatus(BaseModel):
    module: Literal["printers_paper"] = "printers_paper"
    status: Literal["development"] = "development"
    message: str
