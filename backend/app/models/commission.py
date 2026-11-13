# ruff: noqa: E501
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import CommissionBase, CommissionEntryKind, CommissionKind, PayoutMethod, PayoutStatus


class CommissionRule(BaseModel):
    """Shifokor foizi qoidasi. `doctor_id`/`service_id` null: hamma. Tanlash: shifokor+xizmat > shifokor > xizmat > umumiy;
    teng bo'lsa `valid_from` kechroq bo'lgani. Foiz (`Percent`) yoki qat'iy summa har sotilgan birlik uchun (`Fixed`)."""

    __tablename__ = "commission_rules"
    __table_args__ = (
        CheckConstraint("(kind = 'Percent' AND percent > 0 AND percent <= 100 AND fixed_amount IS NULL) OR "
                        "(kind = 'Fixed' AND fixed_amount > 0 AND percent IS NULL)", name="kind_value"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="dates_order"),
    )

    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True)
    service_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[CommissionKind] = mapped_column(enum_col(CommissionKind, "kind", 8))
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    fixed_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    base: Mapped[CommissionBase | None] = mapped_column(enum_col(CommissionBase, "base", 10))  # None: sozlama bo'yicha
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class CommissionSettlement(BranchScoped, BaseModel):
    """Oylik hisob-kitob: shifokorning oy bo'yicha foizi yopiladi (yozuvlar qotadi). O'chirilmaydi."""

    __tablename__ = "commission_settlements"

    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True)
    month: Mapped[date] = mapped_column(Date)  # oyning 1-kuni
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    entries_count: Mapped[int] = mapped_column(Integer)


class CommissionEntry(BranchScoped, BaseModel):
    """Foiz yozuvi: to'lov `Paid` bo'lganda `Accrual` (+), qaytarishda `Reversal` (-, proporsional). Qoida nusxalanadi."""

    __tablename__ = "commission_entries"

    kind: Mapped[CommissionEntryKind] = mapped_column(enum_col(CommissionEntryKind, "kind", 9))
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"))
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    refund_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_refunds.id", ondelete="RESTRICT"))
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoice_lines.id", ondelete="RESTRICT"))
    accrual_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("commission_entries.id", ondelete="RESTRICT"))
    rule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("commission_rules.id", ondelete="SET NULL"))
    rule_kind: Mapped[CommissionKind] = mapped_column(enum_col(CommissionKind, "rule_kind", 8))
    rule_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    rule_fixed: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    base_kind: Mapped[CommissionBase | None] = mapped_column(enum_col(CommissionBase, "base_kind", 10))  # hisoblashda ishlatilgan asos (nusxa)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # imzoli: Reversal manfiy
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # imzoli
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    settlement_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("commission_settlements.id", ondelete="RESTRICT"))


class CommissionPayout(BranchScoped, BaseModel):
    """Oy yopilganda foiz to'lovi hujjati (chiqim): Draft -> Approved -> Paid. Naqd to'langanda kassa smenasiga chiqim (`CashMovement`),
    ikkala usulda ham `transactions` ga xarajat yoziladi. O'chirilmaydi."""

    __tablename__ = "commission_payouts"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    settlement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("commission_settlements.id", ondelete="RESTRICT"), unique=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[PayoutStatus] = mapped_column(enum_col(PayoutStatus, "status", 8), default=PayoutStatus.draft)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pay_method: Mapped[PayoutMethod | None] = mapped_column(enum_col(PayoutMethod, "pay_method", 8))
    reference: Mapped[str | None] = mapped_column(String(100))
