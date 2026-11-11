import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import GenderEnum, LabFlag, LabOrderStatus


class LabTest(BaseModel):
    """Tahlil ko'rsatkichi (katalog). Me'yorlar `LabReferenceRange` da (jins va yosh bo'yicha)."""

    __tablename__ = "lab_tests"
    __table_args__ = (Index("uq_lab_tests_code_lower", func.lower(text("code")), unique=True),)

    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(150))
    unit: Mapped[str | None] = mapped_column(String(30))
    category: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class LabReferenceRange(BaseModel):
    """Me'yor oralig'i. `sex` null: ikkala jins; yosh chegaralari (yil, ikkalasi ham kiritilgan) ixtiyoriy.
    Faqat `low` yoki faqat `high` bo'lishi mumkin (masalan, xolesterin <= 5.2)."""

    __tablename__ = "lab_reference_ranges"
    __table_args__ = (
        CheckConstraint("low IS NOT NULL OR high IS NOT NULL", name="has_bound"),
        CheckConstraint("low IS NULL OR high IS NULL OR low <= high", name="low_le_high"),
        CheckConstraint("age_min IS NULL OR age_max IS NULL OR age_min <= age_max", name="age_order"),
    )

    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_tests.id", ondelete="CASCADE"), index=True)
    sex: Mapped[GenderEnum | None] = mapped_column(enum_col(GenderEnum, "range_sex", 10))
    age_min: Mapped[int | None] = mapped_column(Integer)
    age_max: Mapped[int | None] = mapped_column(Integer)
    low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    note: Mapped[str | None] = mapped_column(String(200))


class LabPanel(BaseModel):
    """Natija shabloni (to'plam): bir buyurtmaga birga qo'shiladigan tahlillar (masalan, UQT)."""

    __tablename__ = "lab_panels"
    __table_args__ = (Index("uq_lab_panels_name_lower", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class LabPanelTest(BaseModel):
    __tablename__ = "lab_panel_tests"
    __table_args__ = (UniqueConstraint("panel_id", "test_id"),)

    panel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_panels.id", ondelete="CASCADE"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_tests.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(Integer, default=0)


class LabOrder(BranchScoped, BaseModel):
    """Laboratoriya buyurtmasi. Hech qachon o'chirilmaydi: bekor qilinadi (status)."""

    __tablename__ = "lab_orders"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    doctor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff.id", ondelete="RESTRICT"))
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"))
    status: Mapped[LabOrderStatus] = mapped_column(enum_col(LabOrderStatus, "status", 10), default=LabOrderStatus.ordered)
    notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LabOrderItem(BaseModel):
    """Buyurtmadagi tahlil. Nom, birlik va me'yor nusxalanadi (katalog keyin o'zgarsa ham natija o'zgarmaydi)."""

    __tablename__ = "lab_order_items"
    __table_args__ = (UniqueConstraint("order_id", "test_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_orders.id", ondelete="RESTRICT"), index=True)
    test_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lab_tests.id", ondelete="RESTRICT"))
    position: Mapped[int] = mapped_column(Integer, default=0)  # buyurtmadagi tartib (to'plam tartibi)
    test_name: Mapped[str] = mapped_column(String(150))
    unit: Mapped[str | None] = mapped_column(String(30))
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    flag: Mapped[LabFlag | None] = mapped_column(enum_col(LabFlag, "flag", 8))
    ref_low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    ref_high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    resulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


__all__ = ["LabTest", "LabReferenceRange", "LabPanel", "LabPanelTest", "LabOrder", "LabOrderItem"]
