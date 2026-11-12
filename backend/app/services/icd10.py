"""MKB-10: CSV import (idempotent upsert), qidiruv va kodni tekshirish."""
import csv
import re
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Icd10Code

CODE_RE = re.compile(r"^[A-Z]\d{2}(\.\d{1,2})?$")
STARTER_SOURCE = "starter (namuna)"
STARTER_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "mkb10_starter.csv"


def normalize_code(code: str) -> str:
    return code.strip().upper().replace(",", ".")


def import_csv(db: Session, path: Path, verified: bool = False, source: str | None = None) -> dict[str, int]:
    """CSV ustunlari: code, name_uz[, name_en]. Mavjud kod yangilanadi (idempotent). Noto'g'ri qatorlar o'tkazib yuboriladi.
    `verified`/`source` hamma yozilgan yozuvga qo'yiladi (rasmiy import: true; starter: false)."""
    existing = {c.code: c for c in db.scalars(select(Icd10Code))}
    stats = {"created": 0, "updated": 0, "skipped": 0}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            code = normalize_code(row.get("code") or "")
            name = (row.get("name_uz") or "").strip()
            if not CODE_RE.match(code) or not name:
                stats["skipped"] += 1
                continue
            name_en = (row.get("name_en") or "").strip() or None
            if code in existing:
                rec = existing[code]
                rec.name_uz, rec.name_en, rec.is_active = name, name_en, True
                rec.verified, rec.source = verified, source
                stats["updated"] += 1
            else:
                rec = Icd10Code(code=code, name_uz=name, name_en=name_en, verified=verified, source=source)
                db.add(rec)
                existing[code] = rec
                stats["created"] += 1
    db.flush()
    return stats


def seed_starter(db: Session) -> None:
    """Bo'sh ma'lumotnomaga starter to'plam (to'liq MKB-10 import skripti bilan yuklanadi)."""
    if not db.scalar(select(func.count()).select_from(Icd10Code)) and STARTER_CSV.exists():
        import_csv(db, STARTER_CSV, verified=False, source=STARTER_SOURCE)


def search(db: Session, query: str | None, limit: int = 20) -> list[Icd10Code]:
    stmt = select(Icd10Code).where(Icd10Code.is_active.is_(True)).order_by(Icd10Code.code).limit(limit)
    if query and query.strip():
        q = query.strip()
        like = f"%{q}%"
        stmt = stmt.where(or_(Icd10Code.code.ilike(f"{q}%"), Icd10Code.name_uz.ilike(like), Icd10Code.name_en.ilike(like)))
    return list(db.scalars(stmt))


def code_known(db: Session, code: str) -> bool:
    """Kod yoki uning 3 belgili toifasi (I10.9 -> I10) ma'lumotnomada bor."""
    base = code.split(".")[0]
    return bool(db.scalar(select(func.count()).select_from(Icd10Code).where(Icd10Code.code.in_({code, base}))))
