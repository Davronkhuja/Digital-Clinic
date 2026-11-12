from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Money
from app.schemas.enums import CashShiftStatus

Cash = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class ShiftOpen(BaseModel):
    opening_cash: Cash = Field(Decimal("0"), description="Kassadagi boshlang'ich naqd (UZS)")
    notes: Optional[str] = Field(None, max_length=300)


class ShiftClose(BaseModel):
    counted_cash: Cash = Field(..., description="Smena oxirida kassadagi sanalgan naqd (UZS)")
    notes: Optional[str] = Field(None, max_length=300)


class MethodTotals(BaseModel):
    payments_count: int
    payments_total: Money
    refunds_count: int = 0
    refunds_total: Money = Decimal("0")
    net: Money = Decimal("0")


class OnlineTotals(BaseModel):
    payments_count: int
    payments_total: Money


class ShiftReport(BaseModel):
    shift_id: str
    z_number: Optional[str] = None
    status: CashShiftStatus
    cashier: Optional[str] = None
    opened_at: datetime
    closed_at: Optional[datetime] = None
    opening_cash: Money
    cash: MethodTotals
    card: MethodTotals
    online: dict[str, OnlineTotals]
    sales_total: Money
    refunds_total: Money
    net_total: Money
    expected_cash: Money
    counted_cash: Optional[Money] = None
    difference: Optional[Money] = Field(None, description="sanalgan - kutilgan (manfiy: kamomad)")
    receipts_missing: int = Field(0, description="Fiskal cheki berilmagan to'lovlar soni")
