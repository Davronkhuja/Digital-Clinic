# ruff: noqa: E501
"""Ko'rik xulosasi (AI): lokal LLM, bemor shaxsiy ma'lumotisiz (ism, telefon, PINFL, manzil yuborilmaydi: faqat yosh, jins va klinik matn).
Qoralama shifokor tasdiqlamaguncha tibbiy yozuvga kirmaydi."""
import ipaddress
from datetime import date
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Encounter, EncounterSummary, Patient, Prescription
from app.services.llm import call_llm
from app.services.periods import clinic_today

SYSTEM_PROMPT = (
    "Sen shifokorga yordam beruvchi tibbiy yordamchisan. Berilgan ko'rik yozuvidan o'zbek tilida qisqa (5-8 jumla) tibbiy xulosa tuz: "
    "shikoyat, ob'ektiv holat, tashxis, buyurilgan davo va tavsiyalar. FAQAT berilgan ma'lumotdan foydalan, yangi tashxis, dori yoki "
    "raqam o'ylab topma; ma'lumot yo'q bo'lsa 'ko'rsatilmagan' deb yoz. Bu qoralama: shifokor tekshirib tasdiqlaydi.")


def is_local_llm(base_url: str) -> bool:
    """Lokal/ichki tarmoq LLM: localhost, privat IP, .local/.internal, yoki nuqtasiz xost (docker servis nomi)."""
    host = (urlparse(base_url).hostname or "").lower()
    if not host:
        return False
    if host in ("localhost", "host.docker.internal") or host.endswith((".local", ".internal", ".lan")) or "." not in host:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def _age(birth: date | None, on: date) -> str:
    if not birth:
        return "noma'lum"
    return str(on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day)))


def build_prompt(db: Session, enc: Encounter) -> str:
    patient = db.get(Patient, enc.patient_id)
    rx = db.scalars(select(Prescription).where(Prescription.encounter_id == enc.id, Prescription.deleted_at.is_(None)).order_by(Prescription.created_at)).all()
    gender = {"male": "erkak", "female": "ayol"}.get(patient.gender.value, "noma'lum")
    parts = [f"Bemor: {gender}, yoshi {_age(patient.birth_date, enc.visit_date)}", f"Ko'rik sanasi: {enc.visit_date.isoformat()}",
             f"Shikoyatlar: {enc.complaints or 'ko`rsatilmagan'}", f"Anamnez: {enc.anamnesis or 'ko`rsatilmagan'}", f"Ob'ektiv ko'rik: {enc.examination or 'ko`rsatilmagan'}",
             f"Tashxis: {enc.diagnosis}" + (f" (MKB-10: {enc.icd_code})" if enc.icd_code else ""), f"Tavsiyalar: {enc.recommendations or 'ko`rsatilmagan'}"]
    if rx:
        parts.append("Retseptlar: " + "; ".join(" ".join(x for x in (r.medication, r.dosage, r.frequency, f"{r.duration_days} kun" if r.duration_days else None) if x) for r in rx))
    return "\n".join(parts)


def demo_text(enc: Encounter) -> str:
    return (f"[Demo rejim: AI o'chirilgan, matn statik shablon] Ko'rik {enc.visit_date.isoformat()}. Shikoyatlar: {enc.complaints or 'ko`rsatilmagan'}. "
            f"Tashxis: {enc.diagnosis}. Tavsiyalar: {enc.recommendations or 'ko`rsatilmagan'}.")


def generate(db: Session, user, enc: Encounter) -> EncounterSummary:
    """Qoralama yaratadi (AI o'chiq bo'lsa statik demo). Eski ochiq qoralamalar rad etiladi. Tashqi LLM bemor ma'lumotini olmaydi (lokal yoki ruxsat bilan)."""
    if settings.ai_enabled:
        if not is_local_llm(settings.llm_base_url) and not settings.llm_allow_external_phi:
            raise HTTPException(409, "Qayd xulosasi faqat lokal LLM bilan: LLM_BASE_URL lokal/ichki tarmoqda bo'lishi kerak (yoki LLM_ALLOW_EXTERNAL_PHI=true)")
        text = call_llm([{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": build_prompt(db, enc)}], temperature=0.2, max_tokens=500).strip()
        source, model = "llm", settings.llm_model
        if not text:
            raise HTTPException(502, "AI xizmati bo'sh javob qaytardi")
    else:
        text, source, model = demo_text(enc), "demo", None
    from datetime import UTC, datetime
    for old in db.scalars(select(EncounterSummary).where(EncounterSummary.encounter_id == enc.id, EncounterSummary.status == "Draft")):
        old.status, old.reviewed_at = "Rejected", datetime.now(UTC)
    summary = EncounterSummary(encounter_id=enc.id, text=text[:4000], original_text=text[:4000], status="Draft", source=source, model=model, generated_by=user.id,
                               branch_id=enc.branch_id, created_by=user.id)
    db.add(summary)
    db.flush()
    return summary


__all__ = ["build_prompt", "clinic_today", "demo_text", "generate", "is_local_llm"]
