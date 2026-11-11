import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import (
    LabOrder,
    LabOrderItem,
    LabPanel,
    LabPanelTest,
    LabReferenceRange,
    LabTest,
    Patient,
    Staff,
)
from app.schemas import LabOrderCreate, LabOrderOut, LabTestIn, LabTestOut, LabTestUpdate, PanelIn, PanelOut, PanelUpdate, ResultsIn
from app.schemas.enums import LabOrderStatus
from app.services import audit, lab
from app.services.lookup import get_patient_or_404, resolve_doctor
from app.services.periods import CLINIC_TZ, clinic_today

router = APIRouter()
TAG = "🧪 Laboratory"


def _f(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def _fmt(v: Decimal | None) -> str:
    return format(v.normalize(), "f") if v is not None else ""


def reference_text(low: Decimal | None, high: Decimal | None) -> str | None:
    if low is not None and high is not None:
        return f"{_fmt(low)} - {_fmt(high)}"
    if high is not None:
        return f"<= {_fmt(high)}"
    if low is not None:
        return f">= {_fmt(low)}"
    return None


def _ts(v: datetime | None) -> str | None:
    return v.astimezone(CLINIC_TZ).isoformat() if v else None


# ---------- Katalog ----------

def _test_out(db: Session, t: LabTest) -> dict:
    ranges = db.scalars(select(LabReferenceRange).where(LabReferenceRange.test_id == t.id).order_by(LabReferenceRange.created_at)).all()
    return {
        "id": str(t.id), "code": t.code, "name": t.name, "unit": t.unit, "category": t.category, "is_active": t.is_active,
        "ranges": [{"id": str(r.id), "sex": r.sex, "age_min": r.age_min, "age_max": r.age_max, "low": _f(r.low),
                    "high": _f(r.high), "note": r.note} for r in ranges],
    }


def _replace_ranges(db: Session, test: LabTest, ranges) -> None:
    for r in db.scalars(select(LabReferenceRange).where(LabReferenceRange.test_id == test.id)):
        db.delete(r)
    db.flush()
    for r in ranges:
        db.add(LabReferenceRange(test_id=test.id, sex=r.sex, age_min=r.age_min, age_max=r.age_max, low=r.low, high=r.high,
                                 note=r.note))


@router.get("/lab/tests", tags=[TAG], response_model=List[LabTestOut], summary="Tahlil ko'rsatkichlari va me'yorlari")
def get_lab_tests(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("lab:read"))):
    stmt = select(LabTest).order_by(LabTest.category, LabTest.name)
    if not include_inactive:
        stmt = stmt.where(LabTest.is_active.is_(True))
    return [_test_out(db, t) for t in db.scalars(stmt)]


@router.post("/lab/tests", tags=[TAG], response_model=LabTestOut, status_code=201, summary="Tahlil ko'rsatkichi qo'shish")
def create_lab_test(data: LabTestIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    test = LabTest(code=data.code.strip().upper(), name=data.name.strip(), unit=data.unit, category=data.category,
                   is_active=data.is_active, created_by=user.id)
    db.add(test)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday kodli tahlil allaqachon mavjud")
    _replace_ranges(db, test, data.ranges)
    db.commit()
    return _test_out(db, test)


@router.put("/lab/tests/{test_id}", tags=[TAG], response_model=LabTestOut, summary="Tahlil yoki me'yorlarni o'zgartirish",
            description="Yozilgan natijalar o'zgarmaydi (nom, birlik, me'yor natijaga nusxalangan). "
                        "Tahlil o'chirilmaydi, faolsizlantiriladi.")
def update_lab_test(test_id: uuid.UUID, data: LabTestUpdate, db: Session = Depends(get_db),
                    user: CurrentUser = Depends(require("settings:write"))):
    test = db.get(LabTest, test_id)
    if not test:
        raise HTTPException(404, "Tahlil topilmadi")
    fields = data.model_dump(exclude_unset=True)
    ranges = data.ranges
    fields.pop("ranges", None)
    for key, value in fields.items():
        if key in ("name", "is_active") and value is None:
            continue
        setattr(test, key, value.strip() if key == "name" else value)
    if ranges is not None:
        _replace_ranges(db, test, ranges)
    db.commit()
    return _test_out(db, test)


def _panel_out(db: Session, p: LabPanel) -> dict:
    codes = db.scalars(select(LabTest.code).join(LabPanelTest, LabPanelTest.test_id == LabTest.id)
                       .where(LabPanelTest.panel_id == p.id).order_by(LabPanelTest.position)).all()
    return {"id": str(p.id), "name": p.name, "is_active": p.is_active, "test_codes": list(codes)}


def _set_panel_tests(db: Session, panel: LabPanel, codes: list[str]) -> None:
    tests = {t.code.upper(): t for t in db.scalars(select(LabTest))}
    missing = [c for c in codes if c.strip().upper() not in tests]
    if missing:
        raise HTTPException(422, f"Noma'lum tahlil kodi: {', '.join(missing)}")
    for old in db.scalars(select(LabPanelTest).where(LabPanelTest.panel_id == panel.id)):
        db.delete(old)
    db.flush()
    seen: set[str] = set()
    for pos, code in enumerate(c.strip().upper() for c in codes):
        if code not in seen:
            seen.add(code)
            db.add(LabPanelTest(panel_id=panel.id, test_id=tests[code].id, position=pos))


@router.get("/lab/panels", tags=[TAG], response_model=List[PanelOut], summary="Tahlil to'plamlari (natija shablonlari)")
def get_panels(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require("lab:read"))):
    stmt = select(LabPanel).order_by(LabPanel.name)
    if not include_inactive:
        stmt = stmt.where(LabPanel.is_active.is_(True))
    return [_panel_out(db, p) for p in db.scalars(stmt)]


@router.post("/lab/panels", tags=[TAG], response_model=PanelOut, status_code=201, summary="To'plam qo'shish")
def create_panel(data: PanelIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    panel = LabPanel(name=data.name.strip(), is_active=data.is_active, created_by=user.id)
    db.add(panel)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli to'plam allaqachon mavjud")
    _set_panel_tests(db, panel, data.test_codes)
    db.commit()
    return _panel_out(db, panel)


@router.put("/lab/panels/{panel_id}", tags=[TAG], response_model=PanelOut, summary="To'plamni o'zgartirish")
def update_panel(panel_id: uuid.UUID, data: PanelUpdate, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("settings:write"))):
    panel = db.get(LabPanel, panel_id)
    if not panel:
        raise HTTPException(404, "To'plam topilmadi")
    if data.name:
        panel.name = data.name.strip()
    if data.is_active is not None:
        panel.is_active = data.is_active
    if data.test_codes is not None:
        _set_panel_tests(db, panel, data.test_codes)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli to'plam allaqachon mavjud")
    return _panel_out(db, panel)


# ---------- Buyurtmalar ----------

def order_out(db: Session, order: LabOrder) -> dict:
    patient, doctor = db.get(Patient, order.patient_id), db.get(Staff, order.doctor_id)
    rows = db.execute(select(LabOrderItem, LabTest.code).join(LabTest, LabOrderItem.test_id == LabTest.id)
                      .where(LabOrderItem.order_id == order.id).order_by(LabOrderItem.position)).all()
    return {
        "id": str(order.id), "patient_id": str(order.patient_id), "patient_name": patient.full_name,
        "doctor_id": str(order.doctor_id), "doctor": doctor.full_name,
        "encounter_id": str(order.encounter_id) if order.encounter_id else None, "status": order.status, "notes": order.notes,
        "created_at": _ts(order.created_at), "completed_at": _ts(order.completed_at),
        "items": [{"id": str(i.id), "test_id": str(i.test_id), "code": code, "name": i.test_name, "unit": i.unit,
                   "value": _f(i.value), "flag": i.flag, "ref_low": _f(i.ref_low), "ref_high": _f(i.ref_high),
                   "reference": reference_text(i.ref_low, i.ref_high), "resulted_at": _ts(i.resulted_at)} for i, code in rows],
    }


def _get_order(db: Session, order_id: uuid.UUID) -> LabOrder:
    order = db.get(LabOrder, order_id)
    if not order:
        raise HTTPException(404, "Laboratoriya buyurtmasi topilmadi")
    return order


@router.post("/lab/orders", tags=[TAG], response_model=LabOrderOut, status_code=201, summary="Laboratoriya buyurtmasi",
             description="To'plamlar (`panel_ids`) va/yoki alohida tahlillar (`test_ids`); takrorlari bir marta olinadi.")
def create_order(data: LabOrderCreate, request: Request, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("lab:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    test_ids: dict[uuid.UUID, None] = dict.fromkeys(data.test_ids)
    for pid in data.panel_ids:
        panel = db.get(LabPanel, pid)
        if not panel or not panel.is_active:
            raise HTTPException(422, "To'plam topilmadi yoki faol emas")
        for tid in db.scalars(select(LabPanelTest.test_id).where(LabPanelTest.panel_id == pid).order_by(LabPanelTest.position)):
            test_ids.setdefault(tid)
    tests = []
    for tid in test_ids:
        test = db.get(LabTest, tid)
        if not test or not test.is_active:
            raise HTTPException(422, "Tahlil topilmadi yoki faol emas")
        tests.append(test)
    order = LabOrder(patient_id=patient.id, doctor_id=doctor.id, encounter_id=data.encounter_id, notes=data.notes,
                     branch_id=user.branch_id, created_by=user.id)
    db.add(order)
    db.flush()
    for pos, t in enumerate(tests):
        db.add(LabOrderItem(order_id=order.id, test_id=t.id, position=pos, test_name=t.name, unit=t.unit, created_by=user.id))
    audit.record(db, user, request, "create", "lab_order", order.id, {"patient_id": str(patient.id), "tests": len(tests)})
    db.commit()
    return order_out(db, order)


@router.get("/lab/orders", tags=[TAG], response_model=List[LabOrderOut], summary="Laboratoriya buyurtmalari")
def get_orders(request: Request, patient_id: Optional[uuid.UUID] = None, status: Optional[LabOrderStatus] = None,
               db: Session = Depends(get_db), user: CurrentUser = Depends(require("lab:read"))):
    stmt = select(LabOrder).order_by(LabOrder.created_at.desc())
    if patient_id:
        stmt = stmt.where(LabOrder.patient_id == patient_id)
    if status:
        stmt = stmt.where(LabOrder.status == status)
    result = [order_out(db, o) for o in db.scalars(stmt)]
    audit.record_read(db, user, request, "lab_order", details={"patient_id": str(patient_id) if patient_id else None, "count": len(result)})
    return result


@router.get("/lab/orders/{order_id}", tags=[TAG], response_model=LabOrderOut, summary="Bitta buyurtma")
def get_order(order_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("lab:read"))):
    order = _get_order(db, order_id)
    audit.record_read(db, user, request, "lab_order", order.id, {"patient_id": str(order.patient_id)})
    return order_out(db, order)


@router.put("/lab/orders/{order_id}/results", tags=[TAG], response_model=LabOrderOut, summary="Natijalarni kiritish",
            description="Har natija bemorning jinsi va yoshiga mos me'yor bilan solishtiriladi (`Low`/`Normal`/`High`); mos me'yor "
                        "bo'lmasa `flag` null. Hamma tahlil natijali bo'lsa buyurtma `Completed`. Tuzatish mumkin (audit).")
def put_results(order_id: uuid.UUID, data: ResultsIn, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("lab:write"))):
    order = _get_order(db, order_id)
    if order.status == LabOrderStatus.cancelled:
        raise HTTPException(409, "Bekor qilingan buyurtmaga natija kiritib bo'lmadi")
    patient = db.get(Patient, order.patient_id)
    items = {i.id: i for i in db.scalars(select(LabOrderItem).where(LabOrderItem.order_id == order.id))}
    now = datetime.now(UTC)
    on: date = clinic_today()
    for r in data.results:
        item = items.get(r.item_id)
        if not item:
            raise HTTPException(422, f"Tahlil bu buyurtmada yo'q: {r.item_id}")
        item.value = r.value
        item.flag, item.ref_low, item.ref_high = lab.evaluate(db, item.test_id, patient, r.value, on)
        item.resulted_at = now
    if all(i.value is not None for i in items.values()):
        order.status, order.completed_at = LabOrderStatus.completed, order.completed_at or now
    audit.record(db, user, request, "update", "lab_order", order.id, {"patient_id": str(order.patient_id), "results": len(data.results)})
    db.commit()
    return order_out(db, order)


@router.post("/lab/orders/{order_id}/cancel", tags=[TAG], response_model=LabOrderOut, summary="Buyurtmani bekor qilish",
             description="Faqat natijasi yo'q (`Ordered`) buyurtma; buyurtma o'chirilmaydi.")
def cancel_order(order_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("lab:write"))):
    order = _get_order(db, order_id)
    if order.status != LabOrderStatus.ordered:
        raise HTTPException(409, "Faqat kutilayotgan buyurtmani bekor qilish mumkin")
    if db.scalar(select(LabOrderItem.id).where(LabOrderItem.order_id == order.id, LabOrderItem.value.is_not(None)).limit(1)):
        raise HTTPException(409, "Natijasi kiritilgan buyurtmani bekor qilib bo'lmaydi")
    order.status = LabOrderStatus.cancelled
    audit.record(db, user, request, "update", "lab_order", order.id, {"patient_id": str(order.patient_id), "status": "Cancelled"})
    db.commit()
    return order_out(db, order)
