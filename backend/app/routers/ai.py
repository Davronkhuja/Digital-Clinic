import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403
from app.services.llm import *  # noqa: F401,F403

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
def ai_chat(data: AIMessage, _=Depends(get_current_user)):
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
def ai_status(_=Depends(get_current_user)):
    return {"enabled": settings.ai_enabled, "demo": not settings.ai_enabled}

@router.post("/ai/analyze", tags=["🤖 AI Assistant"], response_model=AnalyzeResponse,
          summary="Klinika statistikasini AI bilan tahlil qilish")
def ai_analyze(data: AnalyzeRequest, _=Depends(get_current_user)):
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

@router.get("/ai/insights", tags=["🤖 AI Assistant"],
         summary="AI tahliliy ma'lumotlar",
         description="Klinika ma'lumotlari asosida AI tavsiyalari.")
def get_ai_insights(_=Depends(get_current_user)):
    return {
        "insights": [
            {"type": "warning", "title": "Yuqori bekor qilishlar", "message": "Bu oyda 23% uchrashuvlar bekor qilindi. SMS eslatmalar yuborish tavsiya etiladi."},
            {"type": "success", "title": "Daromad o'sishi", "message": "Oxirgi oyga nisbatan 12.5% o'sish kuzatildi."},
            {"type": "info", "title": "Eng ko'p murojaat", "message": "Seshanba va Chorshanba kunlari eng ko'p bemor keladi."},
        ]
    }
