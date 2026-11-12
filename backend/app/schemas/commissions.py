import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Money
from app.schemas.enums import CommissionBase, CommissionEntryKind, CommissionKind

Pct = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
Fixed = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class RuleIn(BaseModel):
    doctor_id: Optional[uuid.UUID] = Field(None, description="Bo'lmasa: hamma shifokor")
    service_id: Optional[uuid.UUID] = Field(None, description="Bo'lmasa: hamma xizmat")
    kind: CommissionKind
    percent: Optional[Pct] = None
    fixed_amount: Optional[Fixed] = Field(None, description="Har sotilgan birlik uchun qat'iy summa (UZS)")
    base: CommissionBase = CommissionBase.with_vat
    valid_from: date
    valid_to: Optional[date] = None
    is_active: bool = True

    @model_validator(mode="after")
    def _valid(self):
        if self.kind == CommissionKind.percent and (self.percent is None or self.fixed_amount is not None):
            raise ValueError("Percent qoidasi uchun faqat percent kerak")
        if self.kind == CommissionKind.fixed and (self.fixed_amount is None or self.percent is not None):
            raise ValueError("Fixed qoidasi uchun faqat fixed_amount kerak")
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to valid_from dan oldin bo'lishi mumkin emas")
        return self


class RuleOut(BaseModel):
    id: str
    doctor_id: Optional[str] = None
    doctor: Optional[str] = None
    service_id: Optional[str] = None
    service: Optional[str] = None
    kind: CommissionKind
    percent: Optional[Money] = None
    fixed_amount: Optional[Money] = None
    base: CommissionBase
    valid_from: date
    valid_to: Optional[date] = None
    is_active: bool


class EntryOut(BaseModel):
    id: str
    kind: CommissionEntryKind
    doctor_id: str
    doctor: str
    service: str
    invoice_number: str
    payment_id: str
    refund_id: Optional[str] = None
    rule_kind: CommissionKind
    rule_percent: Optional[Money] = None
    rule_fixed: Optional[Money] = None
    base_amount: Money
    amount: Money
    entry_date: date
    settled: bool


class DoctorTotals(BaseModel):
    doctor_id: str
    doctor: str
    accrued: Money
    reversed: Money
    net: Money
    entries: int
    settled: bool = Field(..., description="Oy shu shifokor uchun yopilganmi")
    settlement_id: Optional[str] = None


class MonthReport(BaseModel):
    month: str
    doctors: List[DoctorTotals]
    total_net: Money


class SettleIn(BaseModel):
    month: str = Field(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$", examples=["2026-11"])
    doctor_id: uuid.UUID


class SettlementOut(BaseModel):
    id: str
    doctor_id: str
    doctor: str
    month: str
    amount: Money
    entries_count: int
