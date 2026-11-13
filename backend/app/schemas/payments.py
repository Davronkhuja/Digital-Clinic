from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Money
from app.schemas.enums import PaymentMethod, PaymentStatus, ReceiptStatus

PayAmount = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class PaymentCreate(BaseModel):
    method: PaymentMethod
    amount: Optional[PayAmount] = Field(None, description="Bo'lmasa: hisob-fakturaning to'lanmagan qoldig'i")
    reference: Optional[str] = Field(None, max_length=100, description="Terminal cheki raqami yoki izoh")


class RefundCreate(BaseModel):
    amount: Optional[PayAmount] = Field(None, description="Bo'lmasa: to'lovning qaytarilmagan qismi to'liq")
    reason: str = Field(..., min_length=3, max_length=300)
    refund_method: Optional[PaymentMethod] = Field(
        None, description="Click to'lovi uchun majburiy: Cash yoki Card (boshqa usulda qaytarish); naqd/karta to'lovida e'tiborsiz")


class RefundOut(BaseModel):
    id: str
    payment_id: str
    amount: Money
    reason: str
    receipt_status: Optional[ReceiptStatus] = None
    receipt_id: Optional[str] = None
    refund_method: Optional[PaymentMethod] = None
    needs_provider_reconcile: bool = False
    created_at: str


class PaymentOut(BaseModel):
    id: str
    invoice_id: str
    invoice_number: str
    method: PaymentMethod
    status: PaymentStatus
    amount: Money
    refunded_amount: Money = Decimal("0")
    reference: Optional[str] = None
    provider_txn_id: Optional[str] = None
    receipt_status: Optional[ReceiptStatus] = None
    receipt_id: Optional[str] = None
    checkout_url: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: str
    refunds: list[RefundOut] = Field(default_factory=list)
