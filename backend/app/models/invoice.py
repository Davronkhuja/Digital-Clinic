import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Sequence, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import InvoiceStatus

invoice_number_seq = Sequence("invoice_number_seq")


class Invoice(BranchScoped, BaseModel):
    """Hisob-faktura. Hech qachon o'chirilmaydi: bekor qilinadi (`Cancelled`). Pul: numeric(14,2).
    `Draft` tahrirlanadi; `Issued` dan keyin qatorlar o'zgarmaydi. Holat to'lovlar bo'yicha `PartiallyPaid`/`Paid`."""

    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint("subtotal >= 0 AND discount_total >= 0 AND total >= 0 AND vat_total >= 0", name="amounts_non_negative"),
        CheckConstraint("total = subtotal - discount_total", name="total_consistent"),
    )

    number: Mapped[str] = mapped_column(String(20), unique=True)  # INV-000123
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="RESTRICT"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"))
    status: Mapped[InvoiceStatus] = mapped_column(enum_col(InvoiceStatus, "status", 14), default=InvoiceStatus.draft, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))  # chegirmasiz yig'indi
    discount_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))  # qator + hisob-faktura chegirmalari
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))  # to'lanadigan summa (QQS bilan)
    vat_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))  # total ichidagi QQS
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # hisob-faktura darajasidagi chegirma (kiritilgan)
    discount_reason: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))


class InvoiceLine(BaseModel):
    """Qator. Xizmat nomi, narx va soliq maydonlari nusxalangan (narxnoma keyin o'zgarsa ham hisob-faktura o'zgarmaydi)."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND unit_price >= 0", name="qty_price_valid"),
        CheckConstraint("line_discount >= 0 AND invoice_discount_share >= 0 AND net_total >= 0 AND vat_amount >= 0",
                        name="amounts_non_negative"),
        CheckConstraint("net_total = quantity * unit_price - line_discount - invoice_discount_share", name="net_consistent"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"))
    doctor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"))  # ijrochi
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(200))
    mxik: Mapped[str] = mapped_column(String(17))
    package_code: Mapped[str] = mapped_column(String(10))
    vat_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    line_discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    invoice_discount_share: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    net_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # qator bo'yicha to'lanadigan (QQS bilan)
    vat_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    # Xizmat bajarilgan vaqt: shunda sarf ombordan yoziladi (qabul `Completed` yoki qator qo'lda belgilanganda)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
