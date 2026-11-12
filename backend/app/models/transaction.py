import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, SoftDeleteMixin, enum_col
from app.schemas.enums import TransactionType


class Transaction(SoftDeleteMixin, BranchScoped, BaseModel):
    """Moliyaviy yozuv. Hech qachon o'chirilmaydi (deleted_at). Pul: numeric(14,2)."""

    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    type: Mapped[TransactionType] = mapped_column(enum_col(TransactionType, "type", 10))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    description: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(60), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT")
    )
    # To'lov/qaytarishdan avtomatik yozilgan daromad/xarajat (qo'lda kiritilganlarda null)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), unique=True)
    refund_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_refunds.id", ondelete="RESTRICT"), unique=True)
