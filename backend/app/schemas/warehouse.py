import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Money
from app.schemas.enums import StockKind

Qty = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


class _ItemFields(BaseModel):
    @field_validator("sku", mode="before", check_fields=False)
    @classmethod
    def _sku(cls, v):
        v = (v or "").strip()
        return v or None


class StockItemIn(_ItemFields):
    name: str = Field(..., min_length=2, max_length=200, examples=["Shprits 5 ml"])
    kind: StockKind = StockKind.supply
    unit: str = Field(..., min_length=1, max_length=20, examples=["dona"])
    sku: Optional[str] = Field(None, max_length=50)
    min_qty: Qty = Decimal(0)
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class StockItemUpdate(_ItemFields):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    kind: Optional[StockKind] = None
    unit: Optional[str] = Field(None, min_length=1, max_length=20)
    sku: Optional[str] = Field(None, max_length=50)
    min_qty: Optional[Qty] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)


class StockItemOut(BaseModel):
    id: str
    name: str
    kind: StockKind
    unit: str
    sku: Optional[str] = None
    min_qty: Money
    is_active: bool
    notes: Optional[str] = None


QtyPositive = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=3)]
Cost = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class ReceiptLineIn(BaseModel):
    item_id: uuid.UUID
    batch_no: str = Field(..., min_length=1, max_length=60, description="Ishlab chiqaruvchi partiya raqami (seriya)")
    expires_on: Optional[date] = Field(None, description="Yaroqlilik muddati (YYYY-MM-DD); muddatsiz bo'lsa bo'sh")
    qty: QtyPositive
    unit_cost: Cost = Field(..., description="Bir birlik kirim narxi (UZS)")

    @field_validator("batch_no")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Partiya raqami bo'sh bo'lmasin")
        return v


class ReceiptIn(BaseModel):
    supplier: Optional[str] = Field(None, max_length=200)
    doc_no: Optional[str] = Field(None, max_length=60, description="Yetkazib beruvchi hujjat (nakladnoy) raqami")
    received_on: Optional[date] = Field(None, description="Kirim sanasi (standart: bugun; kelajak sanasi mumkin emas)")
    notes: Optional[str] = Field(None, max_length=1000)
    lines: List[ReceiptLineIn] = Field(..., min_length=1, max_length=200)


class ReceiptLineOut(BaseModel):
    batch_id: str
    item_id: str
    item: str
    unit: str
    batch_no: str
    expires_on: Optional[date] = None
    qty: Money
    unit_cost: Money
    amount: Money


class ReceiptOut(BaseModel):
    id: str
    supplier: Optional[str] = None
    doc_no: Optional[str] = None
    received_on: date
    notes: Optional[str] = None
    created_at: str
    total: Money
    lines: List[ReceiptLineOut]


class StockRowOut(BaseModel):
    item_id: str
    name: str
    kind: StockKind
    unit: str
    sku: Optional[str] = None
    min_qty: Money
    qty: Money = Field(..., description="Jami qoldiq (muddati o'tganlar ham)")
    usable_qty: Money = Field(..., description="Yaroqli qoldiq (muddati o'tmagan yoki muddatsiz)")
    expired_qty: Money
    value: Money = Field(..., description="Qoldiq qiymati (qoldiq x partiya narxi)")
    low: bool = Field(..., description="Yaroqli qoldiq minimaldan kam")


class BatchOut(BaseModel):
    id: str
    item_id: str
    item: str
    unit: str
    batch_no: str
    expires_on: Optional[date] = None
    days_left: Optional[int] = Field(None, description="Muddatgacha kun (manfiy: o'tgan); muddatsiz: null")
    expired: bool
    received_on: date
    unit_cost: Money
    qty_received: Money
    qty_remaining: Money
    receipt_id: Optional[str] = None


class AlertsOut(BaseModel):
    low_stock: List[StockRowOut]
