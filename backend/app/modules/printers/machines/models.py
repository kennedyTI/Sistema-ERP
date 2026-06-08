"""Models do cadastro de maquinas do modulo Impressoras."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


class PrinterMachine(Base):
    __tablename__ = "printer_machines"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    manufacturer = Column(String(120), nullable=True)
    model = Column(String(120), nullable=True)
    sector = Column(String(120), nullable=True)
    cost_center = Column(String(80), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now_sao_paulo)
    updated_at = Column(DateTime, nullable=False, default=now_sao_paulo, onupdate=now_sao_paulo)
