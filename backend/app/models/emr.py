import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, SoftDeleteMixin, VerifiedMixin, enum_col
from app.schemas.enums import RouteEnum


class Encounter(SoftDeleteMixin, BranchScoped, BaseModel):
    """Ko'rik / EMR yozuvi. Hech qachon o'chirilmaydi (deleted_at)."""

    __tablename__ = "encounters"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"))
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL")
    )
    visit_date: Mapped[date] = mapped_column(Date)
    icd_code: Mapped[str | None] = mapped_column(String(10))
    # Ko'rik bo'limlari (DMED ko'rik kartasi tartibida): shikoyat, anamnez, ko'rik, tashxis, tavsiya
    complaints: Mapped[str | None] = mapped_column(Text)
    anamnesis: Mapped[str | None] = mapped_column(Text)
    examination: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    recall_date: Mapped[date | None] = mapped_column(Date)  # shifokor belgilagan qayta ko'rik sanasi: shu kuni bemorga eslatma
    # DMED API yo'q: ma'lumot qo'lda ko'chiriladi, ko'chirilgani shifokor/qabulxona tomonidan qo'lda belgilanadi
    dmed_copied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dmed_copied_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Prescription(SoftDeleteMixin, BranchScoped, BaseModel):
    """Retsept. Hech qachon o'chirilmaydi (deleted_at)."""

    __tablename__ = "prescriptions"

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"), index=True
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"))
    medication: Mapped[str] = mapped_column(Text)
    dosage: Mapped[str | None] = mapped_column(String(100))
    frequency: Mapped[str | None] = mapped_column(String(100))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    # INN bo'yicha tuzilgan retsept: `medication` ko'rsatish uchun yig'ma matn, `dosage` doza
    inn: Mapped[str | None] = mapped_column(String(200))
    route: Mapped[RouteEnum | None] = mapped_column(enum_col(RouteEnum, "route", 16))
    instructions: Mapped[str | None] = mapped_column(Text)


class ExamTemplate(BaseModel):
    """Ko'rik shabloni: bo'limlarning boshlang'ich matni (shifokor to'ldirishda o'zgartiradi)."""

    __tablename__ = "exam_templates"
    __table_args__ = (Index("uq_exam_templates_name_lower", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(String(120))
    specialty: Mapped[str | None] = mapped_column(String(100))  # bo'lim/mutaxassislik (ixtiyoriy)
    complaints: Mapped[str | None] = mapped_column(Text)
    anamnesis: Mapped[str | None] = mapped_column(Text)
    examination: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class InnDrug(VerifiedMixin, BaseModel):
    """INN (xalqaro nomsiz nom) ma'lumotnomasi. `scripts/import_inn.py` bilan to'ldiriladi."""

    __tablename__ = "inn_drugs"
    __table_args__ = (Index("uq_inn_drugs_inn_lower", func.lower(text("inn")), unique=True),)

    inn: Mapped[str] = mapped_column(String(200))
    group_uz: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
