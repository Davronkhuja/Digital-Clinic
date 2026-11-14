# ruff: noqa: E501
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, Sequence, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped, enum_col
from app.schemas.enums import StockKind, StockMovementKind, TransferStatus


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


class StockReceipt(BranchScoped, BaseModel):
    """Kirim hujjati (yetkazib beruvchidan). O'zgarmaydi va o'chirilmaydi: tuzatish chiqim/tuzatish harakati bilan."""

    __tablename__ = "stock_receipts"

    supplier: Mapped[str | None] = mapped_column(String(200))
    doc_no: Mapped[str | None] = mapped_column(String(60))
    received_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)


class StockBatch(BranchScoped, BaseModel):
    """Partiya: bir kirim qatori. Qoldiq filial bo'yicha partiyada saqlanadi; `expires_on` bo'yicha FEFO (birinchi tugaydigan birinchi chiqadi).
    `unit_cost` kirim narxi (tannarx hisobi uchun); filiallar orasida ko'chirilganda saqlanadi."""

    __tablename__ = "stock_batches"
    __table_args__ = (
        CheckConstraint("qty_received > 0", name="qty_received_positive"),
        CheckConstraint("qty_remaining >= 0 AND qty_remaining <= qty_received", name="qty_remaining_range"),
        CheckConstraint("unit_cost >= 0", name="unit_cost_non_negative"),
        Index("ix_stock_batches_fefo", "branch_id", "item_id", "expires_on"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="RESTRICT"), index=True)
    receipt_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_receipts.id", ondelete="RESTRICT"))
    batch_no: Mapped[str] = mapped_column(String(60))
    expires_on: Mapped[date | None] = mapped_column(Date)       # null: muddatsiz (masalan, asbob)
    received_on: Mapped[date] = mapped_column(Date)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    qty_received: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(14, 3))


class StockMovement(BranchScoped, BaseModel):
    """Qoldiq harakatlari jurnali (faqat qo'shiladi). `qty` ishorali: kirim +, chiqim -. Qoldiq = partiyalar yig'indisi,
    jurnal esa uning isboti (har partiya uchun harakatlar yig'indisi qoldiqqa teng)."""

    __tablename__ = "stock_movements"
    __table_args__ = (Index("ix_stock_movements_item", "branch_id", "item_id", "created_at"),)

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="RESTRICT"))
    batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[StockMovementKind] = mapped_column(enum_col(StockMovementKind, "kind", 12))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))      # harakat paytidagi partiya narxi (nusxa)
    reason: Mapped[str | None] = mapped_column(String(300))
    ref_type: Mapped[str | None] = mapped_column(String(30))       # receipt, invoice, transfer ...
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class ServiceMaterial(BaseModel):
    """Xizmatga bog'langan sarf normasi: xizmat ko'rsatilganda shu miqdor material ketadi (bir marta ko'rsatishga).
    Tannarx shu normadan va ombordagi narxdan avtomatik hisoblanadi."""

    __tablename__ = "service_materials"
    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        Index("uq_service_materials_service_item", "service_id", "item_id", unique=True),
    )

    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("services.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="RESTRICT"))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))


class StockShortage(BranchScoped, BaseModel):
    """To'lov paytida ombor yetmagan material (to'lov to'xtamaydi): kirimdan keyin `resolve` bilan FEFO bo'yicha yoziladi."""

    __tablename__ = "stock_shortages"
    __table_args__ = (CheckConstraint("qty_missing > 0", name="qty_missing_positive"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT"), index=True)
    invoice_line_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invoice_lines.id", ondelete="RESTRICT"))
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="RESTRICT"))
    qty_missing: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


stock_transfer_number_seq = Sequence("stock_transfer_number_seq")


class StockTransfer(BaseModel):
    """Filiallar orasida ko'chirish hujjati. Yuborilganda manba filial qoldig'i FEFO bo'yicha kamayadi (`TransferOut`), qabul qilinganda
    qabul qiluvchi filialda xuddi shu partiya raqami, muddati va narxi bilan yangi partiya paydo bo'ladi (`TransferIn`).
    Qabul qilinmaguncha manba filial bekor qilishi mumkin (qoldiq qaytadi). O'chirilmaydi."""

    __tablename__ = "stock_transfers"
    __table_args__ = (CheckConstraint("from_branch_id <> to_branch_id", name="different_branches"),)

    number: Mapped[str] = mapped_column(String(20), unique=True)
    from_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), index=True)
    to_branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), index=True)
    status: Mapped[TransferStatus] = mapped_column(enum_col(TransferStatus, "status", 10), default=TransferStatus.sent)
    notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))


class StockTransferLine(BaseModel):
    """Ko'chirish qatori: manba partiyadan olingan miqdor (partiya raqami, muddat, narx nusxalangan)."""

    __tablename__ = "stock_transfer_lines"
    __table_args__ = (CheckConstraint("qty > 0", name="qty_positive"),)

    transfer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_transfers.id", ondelete="RESTRICT"), index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_items.id", ondelete="RESTRICT"))
    source_batch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"))
    dest_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stock_batches.id", ondelete="RESTRICT"))
    batch_no: Mapped[str] = mapped_column(String(60))
    expires_on: Mapped[date | None] = mapped_column(Date)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3))
