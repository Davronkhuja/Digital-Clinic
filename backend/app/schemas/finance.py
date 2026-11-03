from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# Finance
class TransactionCreate(BaseModel):
    type: TransactionType = Field(..., examples=["income"])
    amount: float = Field(..., gt=0, examples=[250000])
    description: str = Field(..., examples=["Konsultatsiya to'lovi"])
    patient_name: Optional[str] = Field(None, examples=["Aziza Karimova"])
    category: str = Field(..., examples=["Consultation"])
    date: str = Field(..., examples=["2026-02-23"])

class Transaction(TransactionCreate):
    id: str
    created_at: str
