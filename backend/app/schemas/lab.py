import uuid
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import GenderEnum, LabFlag, LabOrderStatus


class RangeIn(BaseModel):
    sex: Optional[GenderEnum] = Field(None, description="Bo'lmasa: ikkala jins")
    age_min: Optional[int] = Field(None, ge=0, le=150)
    age_max: Optional[int] = Field(None, ge=0, le=150)
    low: Optional[Decimal] = None
    high: Optional[Decimal] = None
    note: Optional[str] = Field(None, max_length=200)

    @model_validator(mode="after")
    def _valid(self):
        if self.low is None and self.high is None:
            raise ValueError("low yoki high ko'rsatilishi kerak")
        if self.low is not None and self.high is not None and self.low > self.high:
            raise ValueError("low high dan katta bo'lmasligi kerak")
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min age_max dan katta bo'lmasligi kerak")
        return self


class RangeOut(RangeIn):
    id: str
    low: Optional[float] = None
    high: Optional[float] = None


class LabTestIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=30, examples=["HGB"])
    name: str = Field(..., min_length=2, max_length=150, examples=["Gemoglobin"])
    unit: Optional[str] = Field(None, max_length=30, examples=["g/L"])
    category: Optional[str] = Field(None, max_length=60)
    is_active: bool = True
    ranges: List[RangeIn] = Field(default_factory=list)


class LabTestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    unit: Optional[str] = Field(None, max_length=30)
    category: Optional[str] = Field(None, max_length=60)
    is_active: Optional[bool] = None
    ranges: Optional[List[RangeIn]] = Field(None, description="Yuborilsa, me'yorlar to'liq almashtiriladi")


class LabTestOut(BaseModel):
    id: str
    code: str
    name: str
    unit: Optional[str] = None
    category: Optional[str] = None
    is_active: bool
    ranges: List[RangeOut]


class PanelIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, examples=["Umumiy qon tahlili (UQT)"])
    test_codes: List[str] = Field(..., min_length=1)
    is_active: bool = True


class PanelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    test_codes: Optional[List[str]] = Field(None, min_length=1)
    is_active: Optional[bool] = None


class PanelOut(BaseModel):
    id: str
    name: str
    is_active: bool
    test_codes: List[str]


class LabOrderCreate(BaseModel):
    patient_id: uuid.UUID
    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"])
    encounter_id: Optional[uuid.UUID] = None
    panel_ids: List[uuid.UUID] = Field(default_factory=list)
    test_ids: List[uuid.UUID] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _valid(self):
        if not self.doctor_id and not (self.doctor and self.doctor.strip()):
            raise ValueError("doctor_id yoki doctor ko'rsatilishi kerak")
        if not self.panel_ids and not self.test_ids:
            raise ValueError("Kamida bitta to'plam yoki tahlil tanlang")
        return self


class ResultIn(BaseModel):
    item_id: uuid.UUID
    value: Decimal = Field(..., description="Son qiymati")


class ResultsIn(BaseModel):
    results: List[ResultIn] = Field(..., min_length=1)


class LabItemOut(BaseModel):
    id: str
    test_id: str
    code: str
    name: str
    unit: Optional[str] = None
    value: Optional[float] = None
    flag: Optional[LabFlag] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    reference: Optional[str] = Field(None, description="Me'yor matni: '3.9 - 5.9', '<= 41', '>= 1.0'")
    resulted_at: Optional[str] = None


class LabOrderOut(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor: str
    encounter_id: Optional[str] = None
    status: LabOrderStatus
    notes: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    items: List[LabItemOut]
