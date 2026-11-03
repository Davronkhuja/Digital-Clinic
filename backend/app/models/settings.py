from sqlalchemy import String
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
