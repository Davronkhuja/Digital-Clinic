# ruff: noqa: E501
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Insurer(BaseModel):
    """Sug'urta kompaniyasi (ixtiyoriy tibbiy sug'urta, DMS). O'chirilmaydi, faolsizlantiriladi."""

    __tablename__ = "insurers"
    __table_args__ = (Index("uq_insurers_name_lower", func.lower(text("name")), unique=True), CheckConstraint("payment_days >= 0", name="payment_days_non_negative"))

    name: Mapped[str] = mapped_column(String(200))
    tin: Mapped[str | None] = mapped_column(String(20))               # STIR (INN)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    contact_person: Mapped[str | None] = mapped_column(String(200))
    payment_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")   # reyestrdan keyin necha kunda to'laydi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)


class InsuranceContract(BaseModel):
    """Klinika va sug'urta kompaniyasi shartnomasi: muddat, chegirma, qoplanadigan xizmatlar va limitlar."""

    __tablename__ = "insurance_contracts"
    __table_args__ = (
        UniqueConstraint("insurer_id", "number"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="dates_order"),
        CheckConstraint("discount_percent >= 0 AND discount_percent <= 100", name="discount_range"),
        CheckConstraint("default_coverage_percent > 0 AND default_coverage_percent <= 100", name="coverage_range"),
        CheckConstraint("annual_limit IS NULL OR annual_limit >= 0", name="annual_limit_non_negative"),
        CheckConstraint("per_visit_limit IS NULL OR per_visit_limit >= 0", name="per_visit_limit_non_negative"),
    )

    insurer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurers.id", ondelete="RESTRICT"), index=True)
    number: Mapped[str] = mapped_column(String(60))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")        # klinika narxiga chegirma (sug'urtalangan bemorlar uchun)
    coverage_all: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")             # hamma xizmat qoplanadi (ro'yxatsiz)
    default_coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100, server_default="100")
    annual_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))        # bemor uchun kalendar yil bo'yicha sug'urta ulushi limiti
    per_visit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))     # bitta hisob-fakturadagi sug'urta ulushi limiti
    requires_guarantee: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")       # hisob-faktura uchun kafolat xati shart
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)


class InsuranceContractService(BaseModel):
    """Shartnoma bo'yicha qoplanadigan xizmat va qoplash foizi (qolgan qismini bemor to'laydi)."""

    __tablename__ = "insurance_contract_services"
    __table_args__ = (
        UniqueConstraint("contract_id", "service_id"),
        CheckConstraint("coverage_percent > 0 AND coverage_percent <= 100", name="coverage_range"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("insurance_contracts.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"))
    coverage_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100, server_default="100")
