from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.schemas import AIMessage, AIResponse, AnalyzeRequest, AnalyzeResponse
from app.services import analytics
from app.services.llm import (
    AI_DISCLAIMER,
    ANALYZE_SYSTEM_PROMPT,
    CHAT_SYSTEM_PROMPT,
    DEMO_ANALYSIS,
    DEMO_CHAT_DEFAULT,
    DEMO_CHAT_RESPONSES,
    DEMO_CHAT_SUGGESTIONS,
    call_llm,
)

router = APIRouter()

# ── AI ASSISTANT ──────────────────────────────
@router.post("/ai/chat", tags=["🤖 AI Assistant"],
          summary="AI yordamchi bilan suhbat",
          description="""
Tibbiy savollarga AI yordamchidan javob oling.

⚠️ **Muhim**: Bu AI yordamchi professional tibbiy maslahatni almashtirmaydi.
Faqat ma'lumot olish maqsadida foydalaning.
          """,
          response_model=AIResponse)
def ai_chat(data: AIMessage, user: CurrentUser = Depends(require("ai:use"))):
    if not settings.ai_enabled:
        text = next((v for k, v in DEMO_CHAT_RESPONSES.items() if k in data.message.lower()), DEMO_CHAT_DEFAULT)
        return AIResponse(response=text, demo=True, suggestions=DEMO_CHAT_SUGGESTIONS, disclaimer=AI_DISCLAIMER)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if data.context:
        messages.append({"role": "system", "content": f"Kontekst: {data.context}"})
    messages += [t.model_dump() for t in data.history[-10:]]
    messages.append({"role": "user", "content": data.message})
    text = call_llm(messages, temperature=0.7, max_tokens=1024)
    return AIResponse(response=text, suggestions=[], disclaimer=AI_DISCLAIMER)

@router.get("/ai/status", tags=["🤖 AI Assistant"], summary="AI rejimi (demo yoki LLM)")
def ai_status(user: CurrentUser = Depends(require("ai:use"))):
    return {"enabled": settings.ai_enabled, "demo": not settings.ai_enabled}

@router.post("/ai/analyze", tags=["🤖 AI Assistant"], response_model=AnalyzeResponse,
          summary="Klinika statistikasini AI bilan tahlil qilish")
def ai_analyze(data: AnalyzeRequest, user: CurrentUser = Depends(require("ai:use"))):
    if not settings.ai_enabled:
        return AnalyzeResponse(analysis=DEMO_ANALYSIS, demo=True, disclaimer=AI_DISCLAIMER)
    messages = [
        {"role": "system", "content": ANALYZE_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Quyidagi klinika statistikasini ({data.period}) tahlil qil va amaliy tavsiyalar ber:\n"
            f"{data.stats}\n\nQuyidagilarni ko'rsat: 1) Asosiy xulosalar 2) Muammoli joylar 3) Konkret tavsiyalar")},
    ]
    text = call_llm(messages, temperature=0.6, max_tokens=600)
    return AnalyzeResponse(analysis=text, disclaimer=AI_DISCLAIMER)

@router.get("/ai/insights", tags=["🤖 AI Assistant"], summary="Klinika ma'lumotlaridan tavsiyalar",
            description="Bazadagi haqiqiy ko'rsatkichlardan hosil qilinadi (LLM talab qilinmaydi).")
def get_ai_insights(db: Session = Depends(get_db), user: CurrentUser = Depends(require("analytics:read"))):
    return {"insights": analytics.insights(db, branch_id=user.branch_id)}
