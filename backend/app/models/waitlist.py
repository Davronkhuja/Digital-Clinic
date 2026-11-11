import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import WaitlistStatus


class WaitlistEntry(BranchScoped, BaseModel):
    """Kutish ro'yxati: bemor shifokorning bo'sh vaqtini kutadi (xohlagan sana oralig'ida)."""

    __tablename__ = "waitlist"
    __table_args__ = (
        CheckConstraint("date_to IS NULL OR date_to >= date_from", name="dates_order"),
        # bir bemor bir shifokorni ikki marta kutmasin
        Index("uq_waitlist_waiting", "patient_id", "doctor_id", unique=True, postgresql_where=text("status = 'Waiting'")),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True)
    type: Mapped[str] = mapped_column(String(60))
    date_from: Mapped[date] = mapped_column(Date)  # xohlagan oraliq (klinika sanasi)
    date_to: Mapped[date | None] = mapped_column(Date)  # null: cheklovsiz
    status: Mapped[WaitlistStatus] = mapped_column(enum_col(WaitlistStatus, "status", 10), default=WaitlistStatus.waiting)
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
