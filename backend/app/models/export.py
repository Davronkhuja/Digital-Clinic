# ruff: noqa: E501
from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class ExportColumn(BaseModel):
    """Eksport ustun xaritasi (Sozlamalarda tahrirlanadi): ma'lumot to'plami (`dataset`) ustuni (`key`) tashqi tizimda (1C) qanday sarlavha bilan,
    qaysi tartibda chiqishi va chiqish-chiqmasligi. Yozuv yo'q bo'lsa standart ustunlar ishlatiladi."""

    __tablename__ = "export_columns"
    __table_args__ = (Index("uq_export_columns_dataset_key", "dataset", "key", unique=True),)

    dataset: Mapped[str] = mapped_column(String(30))
    key: Mapped[str] = mapped_column(String(40))
    header: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ExportFormat(BaseModel):
    """Eksport formati (bitta qator): sana ko'rinishi, o'nlik ajratgich va CSV ajratgichi (1C/Excel ruscha sozlamasi uchun odatda `;` va `,`)."""

    __tablename__ = "export_format"
    __table_args__ = (
        CheckConstraint("date_format IN ('iso', 'dmy')", name="date_format_values"),
        CheckConstraint("decimal_separator IN ('.', ',')", name="decimal_separator_values"),
        CheckConstraint("csv_delimiter IN (';', ',', 'tab')", name="csv_delimiter_values"),
    )

    date_format: Mapped[str] = mapped_column(String(3), default="iso", server_default="iso")
    decimal_separator: Mapped[str] = mapped_column(String(1), default=".", server_default=".")
    csv_delimiter: Mapped[str] = mapped_column(String(3), default=";", server_default=";")
