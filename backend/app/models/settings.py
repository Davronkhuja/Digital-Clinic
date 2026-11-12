from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped


class ClinicSettings(BranchScoped, BaseModel):
    """Filial bo'yicha klinika sozlamalari (bitta filialga bitta qator)."""

    __tablename__ = "clinic_settings"

    clinic_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Tashkent")
    language: Mapped[str] = mapped_column(String(5), default="uz")
    # Moliya sozlamalari (Sozlamalar > Moliya): kassir chegirma limiti (%); undan oshig'i finance:discount_override
    discount_limit_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("10"), server_default="10")
