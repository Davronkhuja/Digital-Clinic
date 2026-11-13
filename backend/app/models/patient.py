import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.names import normalize_name
from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import GenderEnum, StatusEnum


class Patient(BranchScoped, BaseModel):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint("pinfl ~ '^[0-9]{14}$'", name="pinfl_format"),
        CheckConstraint("source IS NULL OR source IN ('reklama', 'tavsiya', 'instagram', 'onlayn', 'boshqa')", name="source_values"),
    )

    pinfl: Mapped[str | None] = mapped_column(String(14), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    name_norm: Mapped[str] = mapped_column(String(200), index=True, default="")  # normalize_name(full_name)
    phone: Mapped[str] = mapped_column(String(40), index=True)
    birth_date: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[GenderEnum] = mapped_column(enum_col(GenderEnum, "gender", 10))
    address: Mapped[str | None] = mapped_column(String(300))
    blood_type: Mapped[str | None] = mapped_column(String(5))
    allergies: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(20))  # bemor manbasi: reklama, tavsiya, instagram, onlayn, boshqa
    language: Mapped[str] = mapped_column(String(2), default="uz", server_default="uz")  # xabarlar tili: uz (lotin), ru
    status: Mapped[StatusEnum] = mapped_column(enum_col(StatusEnum, "status", 10), default=StatusEnum.active)
    primary_doctor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id", ondelete="SET NULL")
    )
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="SET NULL")
    )


@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def _sync_name_norm(_mapper, _connection, target: Patient) -> None:
    target.name_norm = normalize_name(target.full_name)
