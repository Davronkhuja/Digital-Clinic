import uuid
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import Money
from app.schemas.enums import TransactionType


class TransactionCreate(BaseModel):
    type: TransactionType = Field(..., examples=["income"])
    amount: Money = Field(..., gt=0, max_digits=14, decimal_places=2, examples=[250000])
    description: str = Field(..., examples=["Konsultatsiya to'lovi"])
    patient_id: Optional[uuid.UUID] = None
    patient_name: Optional[str] = Field(None, examples=["Aziza Karimova"], description="patient_id bo'lmasa, nom bo'yicha")
    category: str = Field(..., examples=["Consultation"])
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["2026-02-23"])


class Transaction(BaseModel):
    id: str
    type: TransactionType
    amount: Money
    description: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    category: str
    date: str
    created_at: str
