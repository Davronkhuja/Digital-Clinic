import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Money
from app.schemas.enums import InvoiceStatus

Percent = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
Amount = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class InvoiceLineIn(BaseModel):
    service_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=999)
    doctor_id: Optional[uuid.UUID] = Field(None, description="Ijrochi shifokor (shifokor foizi uchun); bo'lmasa hisob-faktura shifokori")
    discount_percent: Optional[Percent] = None
    discount_amount: Optional[Amount] = None

    @model_validator(mode="after")
    def _one_discount(self):
        if self.discount_percent is not None and self.discount_amount is not None:
            raise ValueError("Qator chegirmasi: foiz yoki summa (ikkalasi emas)")
        return self


class InvoiceCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    appointment_id: Optional[uuid.UUID] = None
    encounter_id: Optional[uuid.UUID] = None
    lines: List[InvoiceLineIn] = Field(..., min_length=1)
    discount_percent: Optional[Percent] = Field(None, description="Hisob-faktura chegirmasi (qatorlarga proporsional taqsimlanadi)")
    discount_amount: Optional[Amount] = None
    discount_reason: Optional[str] = Field(None, max_length=300, description="Chegirma berilsa majburiy")
    notes: Optional[str] = None
    issue: bool = Field(False, description="true: darhol `Issued` (qatorlar qotadi)")

    @model_validator(mode="after")
    def _one_discount(self):
        if self.discount_percent is not None and self.discount_amount is not None:
            raise ValueError("Hisob-faktura chegirmasi: foiz yoki summa (ikkalasi emas)")
        return self


class InvoiceUpdate(BaseModel):
    """Faqat `Draft`: qatorlar va chegirmalar to'liq almashtiriladi."""

    lines: List[InvoiceLineIn] = Field(..., min_length=1)
    doctor_id: Optional[uuid.UUID] = None
    discount_percent: Optional[Percent] = None
    discount_amount: Optional[Amount] = None
    discount_reason: Optional[str] = Field(None, max_length=300)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _one_discount(self):
        if self.discount_percent is not None and self.discount_amount is not None:
            raise ValueError("Hisob-faktura chegirmasi: foiz yoki summa (ikkalasi emas)")
        return self


class CancelIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class InvoiceLineOut(BaseModel):
    id: str
    service_id: str
    name: str
    mxik: str
    package_code: str
    vat_percent: Money
    unit_price: Money
    quantity: int
    doctor_id: Optional[str] = None
    doctor: Optional[str] = None
    line_discount: Money
    invoice_discount_share: Money
    net_total: Money
    vat_amount: Money


class InvoiceOut(BaseModel):
    id: str
    number: str
    patient_id: str
    patient_name: str
    doctor_id: Optional[str] = None
    doctor: Optional[str] = None
    appointment_id: Optional[str] = None
    encounter_id: Optional[str] = None
    status: InvoiceStatus
    subtotal: Money
    discount_total: Money
    total: Money
    vat_total: Money
    discount_percent: Optional[Money] = None
    discount_reason: Optional[str] = None
    notes: Optional[str] = None
    paid_amount: Money = Decimal("0")
    refunded_amount: Money = Decimal("0")
    balance: Money = Decimal("0")
    issued_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    created_at: str
    lines: List[InvoiceLineOut]
