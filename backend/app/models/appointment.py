import uuid
from datetime import date, time

from sqlalchemy import Date, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import AppointmentStatus


class Appointment(BranchScoped, BaseModel):
    __tablename__ = "appointments"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"), index=True
    )
    date: Mapped[date] = mapped_column(Date, index=True)
    time: Mapped[time] = mapped_column(Time)
    type: Mapped[str] = mapped_column(String(60))
    status: Mapped[AppointmentStatus] = mapped_column(
        enum_col(AppointmentStatus, "status", 12), default=AppointmentStatus.scheduled
    )
    notes: Mapped[str | None] = mapped_column(Text)
