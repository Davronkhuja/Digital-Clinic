import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import CashMovementKind, CashShiftStatus

z_number_seq = Sequence("z_number_seq")


class CashShift(BranchScoped, BaseModel):
    """Kassa smenasi: kassir ochadi (boshlang'ich naqd), naqd/karta to'lovlari va qaytarishlar smenaga bog'lanadi, yopilganda
    sanalgan naqd bilan kutilgani solishtiriladi va Z-hisobot (`z_number`, `z_data` snapshot) qayd etiladi. O'chirilmaydi.
    Bitta kassirda bir vaqtda bitta ochiq smena (qisman unikal indeks)."""

    __tablename__ = "cash_shifts"
    __table_args__ = (
        CheckConstraint("opening_cash >= 0 AND (counted_cash IS NULL OR counted_cash >= 0)", name="cash_non_negative"),
        Index("uq_cash_shifts_one_open_per_user", "opened_by", unique=True, postgresql_where="status = 'Open'"),
    )

    opened_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)  # users.id (FK yo'q, loyiha qoidasi)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[CashShiftStatus] = mapped_column(enum_col(CashShiftStatus, "status", 6), default=CashShiftStatus.open)
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    counted_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    expected_cash: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    z_number: Mapped[str | None] = mapped_column(String(12), unique=True)
    z_data: Mapped[dict | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)


class CashMovement(BranchScoped, BaseModel):
    """Kassadan naqd chiqim (smenaga): inkassatsiya yoki shifokor foizi naqd to'lovi. O'chirilmaydi."""

    __tablename__ = "cash_movements"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_shifts.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[CashMovementKind] = mapped_column(enum_col(CashMovementKind, "kind", 10))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    counterparty: Mapped[str] = mapped_column(String(200))  # qabul qiluvchi
    note: Mapped[str | None] = mapped_column(Text)
    payout_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commission_payouts.id", ondelete="RESTRICT"), unique=True)
