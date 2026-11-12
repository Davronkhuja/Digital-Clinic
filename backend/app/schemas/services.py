import re
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import Money

Vat = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
Price = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
MXIK_RE = re.compile(r"^\d{17}$")
PACKAGE_RE = re.compile(r"^\d{1,10}$")


def _digits(value: Optional[str]) -> Optional[str]:
    """Bo'sh joy/chiziqchalar olib tashlanadi ('1234 5678-...'): faqat raqamlar saqlanadi."""
    if value is None:
        return None
    cleaned = re.sub(r"[\s\-]", "", str(value))
    return cleaned or None


class _ServiceFields(BaseModel):
    @field_validator("mxik", mode="before", check_fields=False)
    @classmethod
    def _mxik(cls, v):
        v = _digits(v)
        if v is not None and not MXIK_RE.match(v):
            raise ValueError("MXIK (IKPU) aniq 17 ta raqamdan iborat bo'lishi kerak")
        return v

    @field_validator("package_code", mode="before", check_fields=False)
    @classmethod
    def _package(cls, v):
        v = _digits(v)
        if v is not None and not PACKAGE_RE.match(v):
            raise ValueError("package_code 1-10 ta raqamdan iborat bo'lishi kerak")
        return v


class ServiceIn(_ServiceFields):
    name: str = Field(..., min_length=2, max_length=200, examples=["Terapevt konsultatsiyasi"])
    category_id: Optional[str] = None
    price: Money = Field(..., ge=0, max_digits=14, decimal_places=2, examples=[150000], description="QQS bilan")
    mxik: Optional[str] = Field(None, examples=["09302001001000000"], description="MXIK (IKPU), 17 raqam")
    package_code: Optional[str] = Field(None, examples=["1500364"])
    vat_percent: Optional[Vat] = Field(None, description="QQS foizi (0 = QQSsiz); narxga kiritilgan")
    is_active: bool = True


class ServiceUpdate(_ServiceFields):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    category_id: Optional[str] = None
    price: Optional[Price] = None
    mxik: Optional[str] = None
    package_code: Optional[str] = None
    vat_percent: Optional[Vat] = None
    is_active: Optional[bool] = None


class ServiceOut(BaseModel):
    id: str
    name: str
    category_id: Optional[str] = None
    category: Optional[str] = None
    price: Money
    mxik: Optional[str] = None
    package_code: Optional[str] = None
    vat_percent: Optional[Money] = None
    is_active: bool
    sellable: bool = Field(..., description="Faol va MXIK, package_code, QQS to'liq: faqat shunday xizmat sotiladi")
    missing: List[str] = Field(default_factory=list, description="Yetishmayotgan maydonlar")


class ServiceCategoryIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    is_active: bool = True


class ServiceCategoryOut(BaseModel):
    id: str
    name: str
    is_active: bool
