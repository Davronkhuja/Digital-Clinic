import uuid
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.enums import RouteEnum


class EMRCreate(BaseModel):
    patient_id: uuid.UUID = Field(..., examples=["3f2b8c1e-0000-0000-0000-000000000000"])
    patient_name: Optional[str] = Field(None, description="E'tiborga olinmaydi")
    doctor_id: Optional[uuid.UUID] = None
    doctor: Optional[str] = Field(None, examples=["Dr. Rustamov"])
    diagnosis: str = Field(..., examples=["Gipertenziya 2-darajali"])
    icd_code: Optional[str] = Field(None, max_length=10, examples=["I10"])
    prescription: str = Field(..., examples=["Amlodipine 5mg kuniga 1 marta"])
    notes: Optional[str] = Field(None, examples=["Qon bosimi nazorat ostida"])
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    appointment_id: Optional[uuid.UUID] = Field(None, description="Berilsa, qabul `Completed` bo'ladi")
    recall_days: Optional[int] = Field(None, ge=1, le=730, description="Necha kundan keyin qayta ko'rik (bemorga eslatma ketadi)")
    visit_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-02-23"])

    @model_validator(mode="after")
    def _doctor_required(self):
        if not self.doctor_id and not (self.doctor and self.doctor.strip()):
            raise ValueError("doctor_id yoki doctor ko'rsatilishi kerak")
        return self


class PrescriptionIn(BaseModel):
    inn: str = Field(..., min_length=2, max_length=200, examples=["amlodipine"])
    dose: str = Field(..., min_length=1, max_length=100, examples=["5 mg"])
    route: RouteEnum = Field(RouteEnum.oral)
    frequency: str = Field(..., min_length=1, max_length=100, examples=["kuniga 1 marta"])
    duration_days: int = Field(..., ge=1, le=365)
    instructions: Optional[str] = Field(None, examples=["Ovqatdan keyin"])


class PrescriptionOut(BaseModel):
    id: str
    encounter_id: str
    inn: Optional[str] = None
    dose: Optional[str] = None
    route: Optional[RouteEnum] = None
    frequency: Optional[str] = None
    duration_days: Optional[int] = None
    instructions: Optional[str] = None
    medication: str
    created_at: str


class EMRRecord(BaseModel):
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor: str
    diagnosis: str
    icd_code: Optional[str] = None
    prescription: str
    notes: Optional[str] = None
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    appointment_id: Optional[str] = None
    recall_date: Optional[str] = None
    prescriptions: List[PrescriptionOut] = Field(default_factory=list)
    dmed_copied_at: Optional[str] = None
    visit_date: str
    created_at: str


class Icd10Out(BaseModel):
    code: str
    name_uz: str
    name_en: Optional[str] = None
    verified: bool = False
    source: Optional[str] = None


class EMRUpdate(BaseModel):
    """Ko'rikni tahrirlash. Yuborilmagan maydonlar o'zgarmaydi; retsept alohida (v1.6.11)."""

    diagnosis: Optional[str] = Field(None, min_length=1)
    icd_code: Optional[str] = Field(None, max_length=10)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    recommendations: Optional[str] = None
    notes: Optional[str] = None
    recall_days: Optional[int] = Field(None, ge=1, le=730, description="Qayta ko'rik muddati (kunlar); null: bekor qilish")


class ExamTemplateIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, examples=["Terapevt: umumiy ko'rik"])
    specialty: Optional[str] = Field(None, max_length=100)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    is_active: bool = True


class ExamTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    specialty: Optional[str] = Field(None, max_length=100)
    complaints: Optional[str] = None
    anamnesis: Optional[str] = None
    examination: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    is_active: Optional[bool] = None


class ExamTemplateOut(ExamTemplateIn):
    id: str


class InnOut(BaseModel):
    inn: str
    group_uz: Optional[str] = None
    verified: bool = False
    source: Optional[str] = None


class VerifyIn(BaseModel):
    """Katalog yozuvlarini tasdiqlash: ro'yxat (`items`) yoki hamma tasdiqlanmaganlar (`all=true`)."""

    items: List[str] = Field(default_factory=list)
    all: bool = False
    source: str = Field(..., min_length=3, max_length=200, examples=["MKB-10 rasmiy ro'yxati bilan solishtirildi, Dr. Karimova"])


class VerifyOut(BaseModel):
    verified: int


class InnIn(BaseModel):
    inn: str = Field(..., min_length=2, max_length=200)
    group_uz: Optional[str] = Field(None, max_length=200)


class CardField(BaseModel):
    key: str
    label: str
    value: Optional[str] = None


class CardPrescription(BaseModel):
    inn: str
    dose: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    duration_days: Optional[int] = None
    instructions: Optional[str] = None
    text: str = Field(..., description="Bir tugma bilan nusxalanadigan yig'ma matn")


class CardLabItem(BaseModel):
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    reference: Optional[str] = None
    flag: Optional[str] = None
    ref_verified: Optional[bool] = None


class EMRCard(BaseModel):
    """Ko'rik kartasi: maydonlar DMED ko'rik kartasi tartibida. Har bo'lim alohida nusxalanadi."""

    record_id: str
    patient: List[CardField]
    visit: List[CardField]
    sections: List[CardField]
    icd_code: Optional[str] = None
    icd_name: Optional[str] = None
    icd_verified: Optional[bool] = None
    prescriptions: List[CardPrescription]
    lab_results: List[CardLabItem]
    dmed_copied_at: Optional[str] = None
    dmed_copied_by: Optional[str] = None


class DmedMark(BaseModel):
    copied: bool = Field(..., description="true: 'DMED ga ko'chirildi' belgisi qo'yiladi; false: olib tashlanadi")


class AttachmentOut(BaseModel):
    id: str
    patient_id: str
    encounter_id: Optional[str] = None
    filename: str
    content_type: str
    size_bytes: int
    note: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: str
