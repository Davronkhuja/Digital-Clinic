# ruff: noqa: E501
from datetime import date
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import Money

Pct = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
PctPos = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]
Amount = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]


class InsurerIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200, examples=["Kapital Sug'urta"])
    tin: Optional[str] = Field(None, max_length=20, description="STIR (INN)")
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=300)
    contact_person: Optional[str] = Field(None, max_length=200)
    payment_days: int = Field(30, ge=0, le=365, description="Reyestrdan keyin necha kunda to'laydi")
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)


class InsurerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    tin: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=40)
    email: Optional[str] = Field(None, max_length=200)
    address: Optional[str] = Field(None, max_length=300)
    contact_person: Optional[str] = Field(None, max_length=200)
    payment_days: Optional[int] = Field(None, ge=0, le=365)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)


class InsurerOut(BaseModel):
    id: str
    name: str
    tin: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    payment_days: int
    is_active: bool
    notes: Optional[str] = None
    contracts: int = Field(0, description="Shartnomalar soni")


class ContractServiceIn(BaseModel):
    service_id: str
    coverage_percent: PctPos = Decimal(100)


class ContractIn(BaseModel):
    insurer_id: str
    number: str = Field(..., min_length=1, max_length=60)
    valid_from: date
    valid_to: Optional[date] = None
    discount_percent: Pct = Decimal(0)
    coverage_all: bool = False
    default_coverage_percent: PctPos = Decimal(100)
    annual_limit: Optional[Amount] = Field(None, description="Bemor uchun kalendar yil bo'yicha sug'urta ulushi limiti (UZS)")
    per_visit_limit: Optional[Amount] = Field(None, description="Bitta hisob-fakturadagi sug'urta ulushi limiti (UZS)")
    requires_guarantee: bool = False
    is_active: bool = True
    notes: Optional[str] = Field(None, max_length=1000)
    services: List[ContractServiceIn] = Field(default_factory=list, description="Qoplanadigan xizmatlar (coverage_all=false bo'lsa)")

    @model_validator(mode="after")
    def _valid(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
        if self.coverage_all and self.services:
            raise ValueError("coverage_all=true bo'lsa xizmatlar ro'yxati bo'sh bo'lishi kerak (hamma xizmat qoplanadi)")
        if len({s.service_id for s in self.services}) != len(self.services):
            raise ValueError("Xizmat ro'yxatda takrorlangan")
        return self


class ContractUpdate(BaseModel):
    number: Optional[str] = Field(None, min_length=1, max_length=60)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    discount_percent: Optional[Pct] = None
    coverage_all: Optional[bool] = None
    default_coverage_percent: Optional[PctPos] = None
    annual_limit: Optional[Amount] = None
    per_visit_limit: Optional[Amount] = None
    requires_guarantee: Optional[bool] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)
    services: Optional[List[ContractServiceIn]] = Field(None, description="To'liq ro'yxat almashtiriladi")


class ContractServiceOut(BaseModel):
    service_id: str
    service: str
    coverage_percent: Money


class ContractOut(BaseModel):
    id: str
    insurer_id: str
    insurer: str
    number: str
    valid_from: date
    valid_to: Optional[date] = None
    discount_percent: Money
    coverage_all: bool
    default_coverage_percent: Money
    annual_limit: Optional[Money] = None
    per_visit_limit: Optional[Money] = None
    requires_guarantee: bool
    is_active: bool
    notes: Optional[str] = None
    services: List[ContractServiceOut]


class PolicyIn(BaseModel):
    contract_id: str
    number: str = Field(..., min_length=1, max_length=60, description="Polis raqami")
    valid_from: date
    valid_to: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _valid(self):
        if self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
        return self


class PolicyUpdate(BaseModel):
    number: Optional[str] = Field(None, min_length=1, max_length=60)
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(None, max_length=1000)


class PolicyOut(BaseModel):
    id: str
    patient_id: str
    patient: str
    insurer_id: str
    insurer: str
    contract_id: str
    contract: str
    number: str
    valid_from: date
    valid_to: Optional[date] = None
    is_active: bool
    valid_now: bool = Field(..., description="Faol va bugungi sana muddat ichida (shartnoma ham faol va muddatda)")
    discount_percent: Money
    requires_guarantee: bool
    notes: Optional[str] = None


class LetterIn(BaseModel):
    policy_id: str
    number: str = Field(..., min_length=1, max_length=60)
    letter_date: date
    amount_limit: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    service_ids: List[str] = Field(default_factory=list, description="Qamrab olingan xizmatlar (bo'sh: shartnoma bo'yicha hamma qoplanadigan xizmat)")
    notes: Optional[str] = Field(None, max_length=1000)

    @model_validator(mode="after")
    def _valid(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
        if len(set(self.service_ids)) != len(self.service_ids):
            raise ValueError("Xizmat ro'yxatda takrorlangan")
        return self


class LetterUpdate(BaseModel):
    number: Optional[str] = Field(None, min_length=1, max_length=60)
    letter_date: Optional[date] = None
    amount_limit: Optional[Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    service_ids: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=1000)


class LetterCancelIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class LetterServiceOut(BaseModel):
    service_id: str
    service: str


class LetterOut(BaseModel):
    id: str
    number: str
    insurer_id: str
    insurer: str
    policy_id: str
    policy_number: str
    patient_id: str
    patient: str
    letter_date: date
    amount_limit: Money
    used_amount: Money
    remaining: Money
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    status: str = Field(..., description="Active yoki Cancelled")
    state: str = Field(..., description="Active, Expired (muddati o'tgan), Exhausted (limit tugagan) yoki Cancelled")
    cancel_reason: Optional[str] = None
    notes: Optional[str] = None
    services: List[LetterServiceOut] = Field(default_factory=list)
    has_file: bool
    file_name: Optional[str] = None
    file_size: Optional[int] = None


class InsurerPaymentIn(BaseModel):
    insurer_id: str
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    paid_on: Optional[date] = Field(None, description="To'lov sanasi (standart: bugun; kelajak sanasi mumkin emas)")
    reference: Optional[str] = Field(None, max_length=100, description="To'lov topshiriqnomasi raqami")
    notes: Optional[str] = Field(None, max_length=1000)


class InsurerPaymentOut(BaseModel):
    id: str
    insurer_id: str
    insurer: str
    amount: Money
    paid_on: date
    reference: Optional[str] = None
    notes: Optional[str] = None
    reversed: bool
    reverse_reason: Optional[str] = None
    created_at: str


class ReverseIn(BaseModel):
    reason: str = Field(..., min_length=3, max_length=300)


class OpenInvoiceOut(BaseModel):
    invoice_id: str
    number: str
    date: date
    patient: str
    policy: Optional[str] = None
    amount: Money = Field(..., description="Sug'urta ulushi")
    paid: Money = Field(..., description="Kompaniya to'lovlaridan (FIFO) shu hisob-fakturaga taqsimlangan")
    outstanding: Money
    due_date: date = Field(..., description="Hisob-faktura oyi oxiri + kompaniyaning to'lov kunlari")
    days_overdue: int


class AgingOut(BaseModel):
    current: Money
    d1_30: Money
    d31_60: Money
    d61_90: Money
    d90_plus: Money


class DebtOut(BaseModel):
    insurer_id: str
    insurer: str
    payment_days: int
    charged: Money = Field(..., description="Jami sug'urta ulushi (chiqarilgan, bekor qilinmagan hisob-fakturalar)")
    paid: Money = Field(..., description="Kompaniya to'lovlari (bekor qilinmaganlari)")
    balance: Money = Field(..., description="Qarz = hisoblangan - to'langan (manfiy: ortiqcha to'lov)")
    overpaid: Money
    overdue: Money = Field(..., description="Muddati o'tgan qarz")
    aging: AgingOut
    open_invoices: List[OpenInvoiceOut]
