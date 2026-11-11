from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Icd10Code(BaseModel):
    """MKB-10 ma'lumotnomasi. Import skripti (`scripts/import_mkb10.py`) bilan to'ldiriladi."""

    __tablename__ = "icd10_codes"

    code: Mapped[str] = mapped_column(String(10), unique=True)  # I10, E11.9
    name_uz: Mapped[str] = mapped_column(String(300))
    name_en: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
