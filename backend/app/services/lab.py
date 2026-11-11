"""Laboratoriya: me'yor tanlash, natijani me'yor bilan solishtirish, starter katalog."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LabPanel, LabPanelTest, LabReferenceRange, LabTest, Patient
from app.schemas.enums import GenderEnum, LabFlag

STARTER_JSON = Path(__file__).resolve().parent.parent.parent / "data" / "lab_starter.json"


def pick_range(ranges: list[LabReferenceRange], sex: GenderEnum, age: int | None) -> LabReferenceRange | None:
    """Bemorga mos me'yor: jins mos yoki ko'rsatilmagan, yosh oralig'iga tushadigan. Jinsga xos va tor yosh oralig'i afzal.
    Yosh noma'lum bo'lsa yosh chegarali me'yor tanlanmaydi (noto'g'ri me'yor bilan solishtirishdan ko'ra 'me'yor yo'q')."""
    best, best_score = None, None
    for r in ranges:
        if r.sex is not None and r.sex != sex:
            continue
        if (r.age_min is not None or r.age_max is not None) and age is None:
            continue
        if age is not None and ((r.age_min is not None and age < r.age_min) or (r.age_max is not None and age > r.age_max)):
            continue
        span = (r.age_max if r.age_max is not None else 150) - (r.age_min if r.age_min is not None else 0)
        score = (1 if r.sex is not None else 0, -span)
        if best_score is None or score > best_score:
            best, best_score = r, score
    return best


def classify(value: Decimal, low: Decimal | None, high: Decimal | None) -> LabFlag:
    if low is not None and value < low:
        return LabFlag.low
    if high is not None and value > high:
        return LabFlag.high
    return LabFlag.normal


def evaluate(db: Session, test_id, patient: Patient, value: Decimal, on: date) -> tuple[LabFlag | None, Decimal | None, Decimal | None]:
    """(flag, ref_low, ref_high). Mos me'yor bo'lmasa flag None."""
    ranges = list(db.scalars(select(LabReferenceRange).where(LabReferenceRange.test_id == test_id)))
    born = patient.birth_date
    age = None
    if born:
        age = on.year - born.year - ((on.month, on.day) < (born.month, born.day))
    rng = pick_range(ranges, patient.gender, age)
    if not rng:
        return None, None, None
    return classify(value, rng.low, rng.high), rng.low, rng.high


def seed_starter(db: Session) -> None:
    """Bo'sh katalogga ~24 ta oddiy ko'rsatkich va 3 ta to'plam. Me'yorlar odatda qabul qilingan kattalar (18+)
    qiymatlari: klinika va laboratoriya tasdiqlashi, kerak bo'lsa Sozlamalarda tahrirlashi shart."""
    if db.scalar(select(func.count()).select_from(LabTest)) or not STARTER_JSON.exists():
        return
    data = json.loads(STARTER_JSON.read_text(encoding="utf-8"))
    by_code: dict[str, LabTest] = {}
    for item in data["tests"]:
        test = LabTest(code=item["code"], name=item["name"], unit=item["unit"], category=item["category"])
        db.add(test)
        db.flush()
        by_code[item["code"]] = test
        for r in item["ranges"]:
            db.add(LabReferenceRange(test_id=test.id, sex=GenderEnum(r["sex"]) if r.get("sex") else None,
                                     age_min=r.get("age_min"), age_max=r.get("age_max"),
                                     low=Decimal(str(r["low"])) if "low" in r else None,
                                     high=Decimal(str(r["high"])) if "high" in r else None))
    for panel in data["panels"]:
        p = LabPanel(name=panel["name"])
        db.add(p)
        db.flush()
        for pos, code in enumerate(panel["tests"]):
            db.add(LabPanelTest(panel_id=p.id, test_id=by_code[code].id, position=pos))
    db.flush()


