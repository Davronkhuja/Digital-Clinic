from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, enum_col
from app.schemas.enums import StockKind


class StockItem(BaseModel):
    """Ombor katalogi: dori yoki sarf materiali. Hamma filialga umumiy (qoldiq esa filial bo'yicha, partiyalarda).
    O'chirilmaydi, faolsizlantiriladi. Miqdor 3 xona aniqlikda (ml, g, dona)."""

    __tablename__ = "stock_items"
    __table_args__ = (
        CheckConstraint("min_qty >= 0", name="min_qty_non_negative"),
        Index("uq_stock_items_name_lower", func.lower(text("name")), unique=True),
        Index("uq_stock_items_sku_lower", func.lower(text("sku")), unique=True, postgresql_where=text("sku IS NOT NULL")),
    )

    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[StockKind] = mapped_column(enum_col(StockKind, "kind", 10), default=StockKind.supply)
    unit: Mapped[str] = mapped_column(String(20))
    sku: Mapped[str | None] = mapped_column(String(50))
    min_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0, server_default="0")  # shu qoldiqdan kam bo'lsa ogohlantirish
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text)
