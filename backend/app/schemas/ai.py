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
