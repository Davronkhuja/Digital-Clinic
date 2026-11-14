import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Encounter, EncounterSummary
from app.schemas import AIMessage, AIResponse, AnalyzeRequest, AnalyzeResponse, SummaryApproveIn, SummaryState
from app.services import ai_summary, analytics, audit
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


# ---------- Ko'rik xulosasi (AI qoralama, shifokor tasdig'i) ----------

def _enc(db: Session, record_id: uuid.UUID) -> Encounter:
    enc = db.scalar(select(Encounter).where(Encounter.id == record_id, Encounter.deleted_at.is_(None)))
    if not enc:
        raise HTTPException(404, "Yozuv topilmadi")
    return enc


def _summary_out(s: EncounterSummary) -> dict:
    iso = lambda d: d.isoformat() if d else None          # noqa: E731
    return {"id": str(s.id), "status": s.status, "source": s.source, "demo": s.source == "demo", "model": s.model, "text": s.text, "original_text": s.original_text,
            "edited": s.edited, "generated_by": str(s.generated_by) if s.generated_by else None, "reviewed_by": str(s.reviewed_by) if s.reviewed_by else None,
            "reviewed_at": iso(s.reviewed_at), "created_at": iso(s.created_at)}


def _state(db: Session, enc: Encounter, user: CurrentUser) -> dict:
    rows = db.scalars(select(EncounterSummary).where(EncounterSummary.encounter_id == enc.id).order_by(EncounterSummary.created_at.desc())).all()
    draft = next((r for r in rows if r.status == "Draft"), None)
    approved = next((r for r in rows if r.status == "Approved"), None)
    return {"ai_enabled": settings.ai_enabled, "can_review": "emr:write" in user.permissions and enc.doctor_id == user.staff_id, "draft": _summary_out(draft) if draft else None, "approved": _summary_out(approved) if approved else None,
            "disclaimer": AI_DISCLAIMER}


@router.get("/emr/{record_id}/ai-summary", tags=["🤖 AI Assistant"], response_model=SummaryState, summary="Ko'rik xulosasi: qoralama va tasdiqlangani",
            description="Qoralama tibbiy yozuvga kirmagan; tasdiqlangani shifokor tekshirgan matn. EMR o'qish auditga yoziladi.")
def get_summary(record_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:read"))):
    enc = _enc(db, record_id)
    audit.record_read(db, user, request, "ai_summary", enc.id, {"patient_id": str(enc.patient_id)})
    return _state(db, enc, user)


@router.post("/emr/{record_id}/ai-summary", tags=["🤖 AI Assistant"], response_model=SummaryState, status_code=201, summary="Xulosa qoralamasini yaratish",
             description="`AI_ENABLED=true`: lokal LLM (OpenAI-mos); bemor ismi, telefoni, PINFL va manzili yuborilmaydi (faqat yosh, jins va klinik matn); tashqi (lokal bo'lmagan) "
                         "LLM bemor ma'lumotini olmaydi (409). `AI_ENABLED=false`: statik demo shablon (tasdiqlanmaydi). Eski ochiq qoralama rad etiladi. "
                         "Qoralama shifokor tasdiqlamaguncha tibbiy yozuvga kirmaydi. `ai:use` va `emr:read`.")
def create_summary(record_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("ai:use", "emr:read"))):
    enc = _enc(db, record_id)
    s = ai_summary.generate(db, user, enc)
    audit.record(db, user, request, "create", "ai_summary", s.id, {"encounter_id": str(enc.id), "source": s.source, "model": s.model, "patient_id": str(enc.patient_id)})
    db.commit()
    return _state(db, enc, user)


def _own_draft(db: Session, user: CurrentUser, record_id: uuid.UUID, summary_id: uuid.UUID) -> tuple[Encounter, EncounterSummary]:
    enc = _enc(db, record_id)
    s = db.get(EncounterSummary, summary_id)
    if not s or s.encounter_id != enc.id:
        raise HTTPException(404, "Xulosa topilmadi")
    if s.status != "Draft":
        raise HTTPException(409, f"Xulosa holati {s.status}: faqat qoralama ko'rib chiqiladi")
    if enc.doctor_id != user.staff_id:
        raise HTTPException(403, "Xulosani faqat ko'rik shifokori tasdiqlaydi yoki rad etadi")
    return enc, s


@router.post("/emr/{record_id}/ai-summary/{summary_id}/approve", tags=["🤖 AI Assistant"], response_model=SummaryState, summary="Xulosani tasdiqlash (shifokor)",
             description="Faqat ko'rik shifokori (`emr:write`). `text` berilsa tahrirlangan matn saqlanadi (tahrir belgisi). Demo (statik) matn tasdiqlanmaydi (409). "
                         "Tasdiqlangach tibbiy yozuvga kiradi; eski tasdiqlangani `Superseded`. Auditga yoziladi.")
def approve_summary(record_id: uuid.UUID, summary_id: uuid.UUID, request: Request, data: SummaryApproveIn | None = None, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("emr:write"))):
    from datetime import UTC, datetime
    enc, s = _own_draft(db, user, record_id, summary_id)
    if s.source == "demo":
        raise HTTPException(409, "Demo rejimdagi matn tasdiqlanmaydi: AI_ENABLED=true bilan haqiqiy xulosa yarating")
    text = (data.text.strip() if data and data.text else None) or s.text
    for old in db.scalars(select(EncounterSummary).where(EncounterSummary.encounter_id == enc.id, EncounterSummary.status == "Approved")):
        old.status = "Superseded"
    s.edited = text != s.original_text
    s.text, s.status, s.reviewed_by, s.reviewed_at = text, "Approved", user.id, datetime.now(UTC)
    audit.record(db, user, request, "update", "ai_summary", s.id, {"encounter_id": str(enc.id), "status": "Approved", "edited": s.edited, "patient_id": str(enc.patient_id)})
    db.commit()
    return _state(db, enc, user)


@router.post("/emr/{record_id}/ai-summary/{summary_id}/reject", tags=["🤖 AI Assistant"], response_model=SummaryState, summary="Xulosani rad etish (shifokor)")
def reject_summary(record_id: uuid.UUID, summary_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("emr:write"))):
    from datetime import UTC, datetime
    enc, s = _own_draft(db, user, record_id, summary_id)
    s.status, s.reviewed_by, s.reviewed_at = "Rejected", user.id, datetime.now(UTC)
    audit.record(db, user, request, "update", "ai_summary", s.id, {"encounter_id": str(enc.id), "status": "Rejected"})
    db.commit()
    return _state(db, enc, user)
