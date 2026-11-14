import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings

logger = logging.getLogger("digital_clinic")

AI_DISCLAIMER = ("Bu AI yordamchi faqat ma'lumot maqsadida. "
                 "Professional tibbiy maslahat uchun shifokorga murojaat qiling.")
CHAT_SYSTEM_PROMPT = (
    "Sen Digital Clinic tizimining tibbiy AI yordamchisisan. O'zbek tilida qisqa, aniq va professional javob ber. "
    "Tibbiy terminologiyadan foydalanishing mumkin, lekin oddiy til bilan tushuntir. "
    "Har doim \"shifokorga murojaat qiling\" deb ta'kidla.")
ANALYZE_SYSTEM_PROMPT = (
    "Sen tibbiy klinika uchun analitik AI yordamchisisan. Berilgan statistika asosida qisqa (200-250 so'z) "
    "va amaliy tavsiyalar ber. O'zbek tilida yoz. Raqamli ma'lumotlarga asoslan.")

DEMO_CHAT_RESPONSES = {
    "qon": "Qon bosimi ko'tarilganda: darhol shifokorga murojaat qiling. Amlodipine yoki boshqa antihipertenziv dorilar buyurilishi mumkin.",
    "diabet": "Qandli diabetda qon shakarini nazorat qilish juda muhim. Metformin va diet terapiyasi ko'p qo'llaniladi.",
    "dori": "Dori buyurish uchun shifokor konsultatsiyasi zarur. Bemor anamnezini tekshiring.",
}
DEMO_CHAT_DEFAULT = "Bemorning holati kuzatuv ostida bo'lishi tavsiya etiladi. Qo'shimcha tekshiruvlar o'tkazish kerak bo'lishi mumkin."
DEMO_CHAT_SUGGESTIONS = [
    "Qo'shimcha qon tahlili buyuring",
    "Blood pressure monitoring tavsiya eting",
    "Ovqatlanish rejimini ko'rib chiqing",
]
DEMO_ANALYSIS = (
    "1) Asosiy xulosalar: bemorlar oqimi va daromad o'sish tendensiyasida.\n"
    "2) Muammoli joylar: uchrashuvlarning bekor qilinish ulushi yuqori.\n"
    "3) Tavsiyalar: SMS eslatmalar yuborish, eng band kunlarda qabul jadvalini kengaytirish, "
    "eng ko'p uchraydigan tashxislar bo'yicha profilaktika dasturini ishga tushirish.")

def call_llm(messages: list, temperature: float, max_tokens: int) -> str:
    """LLM'ga so'rov yuboradi; xatolarni mos HTTP statuslarga o'giradi."""
    if settings.llm_require_key and not settings.llm_api_key:
        raise HTTPException(status_code=503, detail="AI xizmati sozlanmagan (settings.llm_api_key)")
    try:
        res = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"} if settings.llm_api_key else {},
            json={"model": settings.llm_model, "messages": messages,
                  "temperature": temperature, "max_tokens": max_tokens, "stream": False},
            timeout=settings.llm_timeout,
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI xizmati javob bermadi (timeout)")
    except httpx.HTTPError as e:
        logger.error("LLM ulanish xatosi: %s", e)
        raise HTTPException(status_code=502, detail="AI xizmatiga ulanib bo'lmadi")
    if res.status_code != 200:
        logger.error("LLM xatosi %s: %s", res.status_code, res.text[:300])
        raise HTTPException(status_code=502, detail=f"AI xizmati xatosi (HTTP {res.status_code})")
    try:
        return res.json()["choices"][0]["message"]["content"] or "Javob olinmadi."
    except (KeyError, IndexError, ValueError):
        raise HTTPException(status_code=502, detail="AI xizmati noto'g'ri javob qaytardi")
