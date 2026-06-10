"""Models do cadastro de modelos e maquinas do modulo Impressoras."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.app.core.database import Base
from backend.app.core.timezone import now_sao_paulo


class PrinterModel(Base):
    __tablename__ = "printers_models"
    __table_args__ = (
        UniqueConstraint("manufacturer", "name", name="uq_printers_models_manufacturer_name"),
    )

    id = Column(Integer, primary_key=True)
    manufacturer = Column(String(120), nullable=False)
    name = Column(String(120), nullable=False)
    type = Column(String(80), nullable=True)
    color_mode = Column(String(40), nullable=True)
    url_imagem = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now_sao_paulo)
    updated_at = Column(DateTime, nullable=False, default=now_sao_paulo, onupdate=now_sao_paulo)

    machines = relationship("PrinterMachine", back_populates="printer_model")


class PrinterMachine(Base):
    __tablename__ = "printer_machines"

    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    ip_address = Column(String(45), nullable=False, unique=True, index=True)
    model_id = Column(Integer, ForeignKey("printers_models.id"), nullable=True, index=True)
    sector = Column(String(120), nullable=True)
    cost_center = Column(String(80), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=now_sao_paulo)
    updated_at = Column(DateTime, nullable=False, default=now_sao_paulo, onupdate=now_sao_paulo)

    printer_model = relationship("PrinterModel", back_populates="machines")
    status_operacional_atual = relationship(
        "StatusImpressora",
        back_populates="maquina",
        uselist=False,
        cascade="all, delete-orphan",
    )
    logs_operacionais = relationship(
        "LogImpressora",
        back_populates="maquina",
        cascade="all, delete-orphan",
    )

    @property
    def manufacturer(self) -> str | None:
        return self.printer_model.manufacturer if self.printer_model else None

    @property
    def model(self) -> str | None:
        return self.printer_model.name if self.printer_model else None

    @property
    def type(self) -> str | None:
        return self.printer_model.type if self.printer_model else None

    @property
    def color_mode(self) -> str | None:
        return self.printer_model.color_mode if self.printer_model else None
