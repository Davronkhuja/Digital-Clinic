from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.enums import Channel, ConsentStatus, MessageStatus


class ConsentIn(BaseModel):
    channel: Channel
    granted: bool = Field(..., description="true: rozilik berildi; false: voz kechdi")
    note: Optional[str] = Field(None, max_length=300, description="Masalan: qog'oz rozilik shakli raqami")


class ConsentOut(BaseModel):
    channel: Channel
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    source: Optional[str] = None
    note: Optional[str] = None


class PatientContact(BaseModel):
    patient_id: str
    language: str
    consents: List[ConsentOut]
    telegram_linked: bool


class LanguageIn(BaseModel):
    language: str = Field(..., pattern="^(uz|ru)$")


class TemplateIn(BaseModel):
    body: str = Field(..., min_length=5, max_length=1000)
    is_active: bool = True


class TemplateOut(BaseModel):
    key: str
    language: str
    body: str
    is_active: bool
    is_default: bool = Field(..., description="Sozlamada saqlanmagan: standart matn")
    placeholders: List[str]


class MessageOut(BaseModel):
    id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    channel: Channel
    to_address: str
    kind: str
    language: str
    body: str
    status: MessageStatus
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    attempts: int
    last_error: Optional[str] = None
    skip_reason: Optional[str] = None
    sms_segments: int
    appointment_id: Optional[str] = None


class MessageStats(BaseModel):
    date_from: str
    date_to: str
    by_status: dict[str, int]
    sms_messages: int
    sms_segments: int = Field(..., description="Yuborilgan SMS qismlari soni: xarajat hisobi uchun")
    telegram_messages: int
    by_kind: dict[str, int]
