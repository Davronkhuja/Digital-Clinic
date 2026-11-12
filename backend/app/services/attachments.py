"""Ilova fayllarini tekshirish: tur (magic bytes, kengaytma emas), hajm, xavfsiz nom."""
import re
from dataclasses import dataclass

ALLOWED_LABEL = "PDF, JPG, PNG, DICOM"


@dataclass(frozen=True)
class Detected:
    content_type: str
    ext: str


def detect(data: bytes) -> Detected | None:
    """Faylning haqiqiy turi boshlang'ich baytlar bo'yicha; foydalanuvchi bergan Content-Type va kengaytmaga ishonilmaydi."""
    if data.startswith(b"%PDF-"):
        return Detected("application/pdf", "pdf")
    if data.startswith(b"\xff\xd8\xff"):
        return Detected("image/jpeg", "jpg")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return Detected("image/png", "png")
    if len(data) >= 132 and data[128:132] == b"DICM":
        return Detected("application/dicom", "dcm")
    return None


def safe_filename(name: str | None, ext: str) -> str:
    """Faqat ko'rsatish uchun (saqlash kaliti alohida): yo'l ajratgichlar va boshqaruv belgilari olib tashlanadi."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f\"<>|:*?]", "", base).strip(" .")
    if not base:
        base = f"fayl.{ext}"
    stem, dot, tail = base.rpartition(".")
    if not dot or tail.lower() not in {ext, "jpeg" if ext == "jpg" else ext}:
        stem = base if not dot else stem
        base = f"{stem or 'fayl'}.{ext}"  # kengaytma haqiqiy turga moslanadi (rasm.exe + PNG -> rasm.png)
    return base[:255]
