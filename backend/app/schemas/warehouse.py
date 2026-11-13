from decimal import Decimal
from typing import Annotated, Optional

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
