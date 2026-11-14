# ruff: noqa: E501
from typing import List, Optional  # noqa: F401

from pydantic import BaseModel, EmailStr, Field  # noqa: F401

from app.schemas.enums import *  # noqa: F403


# AI
class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)

class AIMessage(BaseModel):
    message: str = Field(..., max_length=4000, examples=["Bemorning qon bosimi ko'tarilgan. Nima qilish kerak?"])
    context: Optional[str] = Field(None, max_length=2000, examples=["Bemor 54 yoshli, qandli diabet bilan"])
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)

class AnalyzeRequest(BaseModel):
    period: str = Field("month", pattern="^(week|month|year)$")
    stats: str = Field(..., max_length=6000, description="Klinika statistikasi (matn)")

class AnalyzeResponse(BaseModel):
    analysis: str
    demo: bool = False
    disclaimer: str

class AIResponse(BaseModel):
    response: str
    demo: bool = False
    suggestions: List[str]
    disclaimer: str


class SummaryOut(BaseModel):
    id: str
    status: str
    source: str = Field(..., description="llm yoki demo (statik shablon)")
    demo: bool
    model: Optional[str] = None
    text: str
    original_text: str
    edited: bool
    generated_by: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    created_at: str


class SummaryState(BaseModel):
    ai_enabled: bool
    can_review: bool = Field(False, description="Joriy foydalanuvchi shu ko'rikning shifokori (emr:write): tasdiqlay yoki rad eta oladi")
    draft: Optional[SummaryOut] = None
    approved: Optional[SummaryOut] = Field(None, description="Oxirgi tasdiqlangan xulosa (tibbiy yozuvga kirgan)")
    disclaimer: str


class SummaryApproveIn(BaseModel):
    text: Optional[str] = Field(None, min_length=10, max_length=4000, description="Shifokor tahrir qilgan matn (bo'sh: qoralama o'zgarishsiz)")
