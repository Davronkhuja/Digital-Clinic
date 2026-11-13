import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import PaymentMethod, PaymentStatus, ReceiptStatus


class Payment(BranchScoped, BaseModel):
    """To'lov. Hech qachon o'chirilmaydi. Naqd/karta kassada `Paid` yoziladi; Click/Payme `Pending` bo'lib, provayder
    chaqiruvi bilan `Paid`/`Cancelled`. Har `Paid` to'lov fiskal chek bilan yopiladi (`receipt_id`)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("uq_payments_provider_txn", "method", "provider_txn_id", unique=True,
              postgresql_where="provider_txn_id IS NOT NULL"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    method: Mapped[PaymentMethod] = mapped_column(enum_col(PaymentMethod, "method", 6))
    status: Mapped[PaymentStatus] = mapped_column(enum_col(PaymentStatus, "status", 10), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference: Mapped[str | None] = mapped_column(String(100))  # terminal cheki / izoh
    # Provayder (Click/Payme): tranzaksiya ID, holat kodi, xom ma'lumot
    provider_txn_id: Mapped[str | None] = mapped_column(String(100))
    provider_state: Mapped[int | None] = mapped_column(Integer)
    provider_data: Mapped[dict | None] = mapped_column(JSONB)
    # Fiskal chek
    receipt_status: Mapped[ReceiptStatus | None] = mapped_column(enum_col(ReceiptStatus, "receipt_status", 8))
    receipt_id: Mapped[str | None] = mapped_column(String(100))
    receipt_data: Mapped[dict | None] = mapped_column(JSONB)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_shifts.id", ondelete="RESTRICT"), index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentRefund(BranchScoped, BaseModel):
    """To'lovni (to'liq yoki qisman) qaytarish. O'chirilmaydi; qaytarish cheki ham fiskal."""

    __tablename__ = "payment_refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reason: Mapped[str] = mapped_column(Text)
    provider_reason: Mapped[int | None] = mapped_column(Integer)  # Payme bekor qilish sababi kodi
    # Qaytarish usuli: Cash/Card (kassadan) yoki null (provayder o'zi qaytargan, masalan Payme). Click to'lovi kalit kelguncha
    # "boshqa usulda" (Cash/Card) qaytariladi: original to'lovga bog'liq, provayder bilan solishtirish kerak (`needs_provider_reconcile`)
    refund_method: Mapped[PaymentMethod | None] = mapped_column(enum_col(PaymentMethod, "refund_method", 6))
    needs_provider_reconcile: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    shift_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cash_shifts.id", ondelete="RESTRICT"), index=True)
    receipt_status: Mapped[ReceiptStatus | None] = mapped_column(enum_col(ReceiptStatus, "receipt_status", 8))
    receipt_id: Mapped[str | None] = mapped_column(String(100))
    receipt_data: Mapped[dict | None] = mapped_column(JSONB)
