import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, SoftDeleteMixin


class Attachment(SoftDeleteMixin, BranchScoped, BaseModel):
    """Bemor kartasi yoki ko'rikka biriktirilgan fayl (PDF, JPG, PNG, DICOM). Tibbiy yozuv: o'chirilmaydi (`deleted_at`),
    fayl saqlashda qoladi. Baytlar `Storage` da, bu yerda faqat metadata."""

    __tablename__ = "attachments"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patients.id", ondelete="RESTRICT"), index=True)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id", ondelete="RESTRICT"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(60))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    note: Mapped[str | None] = mapped_column(String(300))
