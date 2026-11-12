# ruff: noqa: E501
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import CommissionEntry, CommissionRule, CommissionSettlement, Invoice, Payment, Service, Staff
from app.schemas.commissions import DoctorTotals, EntryOut, MonthReport, RuleIn, RuleOut, SettleIn, SettlementOut
from app.schemas.enums import CommissionEntryKind, StaffRole
from app.services import audit, commissions
from app.services.money import q2
from app.services.periods import clinic_today

router = APIRouter()
TAG = "👨‍⚕️ Doctor commissions"
MANAGE = "commissions:manage"


def _rule_out(db: Session, r: CommissionRule) -> dict:
    doctor = db.get(Staff, r.doctor_id) if r.doctor_id else None
    service = db.get(Service, r.service_id) if r.service_id else None
    return {"id": str(r.id), "doctor_id": str(r.doctor_id) if r.doctor_id else None, "doctor": doctor.full_name if doctor else None,
            "service_id": str(r.service_id) if r.service_id else None, "service": service.name if service else None, "kind": r.kind,
            "percent": r.percent, "fixed_amount": r.fixed_amount, "base": r.base, "valid_from": r.valid_from, "valid_to": r.valid_to,
            "is_active": r.is_active}


def _check_refs(db: Session, data: RuleIn) -> None:
    if data.doctor_id:
        doctor = db.get(Staff, data.doctor_id)
        if not doctor or doctor.role != StaffRole.doctor:
            raise HTTPException(422, "Shifokor topilmadi")
    if data.service_id and not db.get(Service, data.service_id):
        raise HTTPException(422, "Xizmat topilmadi")


@router.get("/commission-rules", tags=[TAG], response_model=List[RuleOut], summary="Shifokor foizi qoidalari")
def list_rules(include_inactive: bool = False, db: Session = Depends(get_db), user: CurrentUser = Depends(require(MANAGE))):
    stmt = select(CommissionRule).order_by(CommissionRule.valid_from.desc(), CommissionRule.created_at.desc())
    if not include_inactive:
        stmt = stmt.where(CommissionRule.is_active.is_(True))
    return [_rule_out(db, r) for r in db.scalars(stmt)]


@router.post("/commission-rules", tags=[TAG], response_model=RuleOut, status_code=201, summary="Qoida qo'shish",
             description="Foiz yoki qat'iy summa; shifokor/xizmat ixtiyoriy (bo'sh: hamma). Tanlash: shifokor+xizmat > shifokor > xizmat > "
                         "umumiy, teng bo'lsa `valid_from` kechroq. Sana oralig'i. Eski yozuvlar o'zgarmaydi (qoida nusxalanadi).")
def create_rule(data: RuleIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require(MANAGE))):
    _check_refs(db, data)
    r = CommissionRule(**data.model_dump(), created_by=user.id)
    db.add(r)
    db.flush()
    audit.record(db, user, request, "create", "commission_rule", r.id, {"kind": r.kind.value, "percent": str(r.percent),
                                                                          "fixed": str(r.fixed_amount), "from": str(r.valid_from)})
    db.commit()
    return _rule_out(db, r)


@router.put("/commission-rules/{rule_id}", tags=[TAG], response_model=RuleOut, summary="Qoidani o'zgartirish yoki o'chirib qo'yish (is_active)")
def update_rule(rule_id: uuid.UUID, data: RuleIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require(MANAGE))):
    r = db.get(CommissionRule, rule_id)
    if not r:
        raise HTTPException(404, "Qoida topilmadi")
    _check_refs(db, data)
    for key, value in data.model_dump().items():
        setattr(r, key, value)
    audit.record(db, user, request, "update", "commission_rule", r.id, {"kind": r.kind.value, "active": r.is_active})
    db.commit()
    return _rule_out(db, r)


def _scope_doctor(user: CurrentUser, doctor_id: uuid.UUID | None) -> uuid.UUID | None:
    """`commissions:manage` hammasini ko'radi; faqat `commissions:read` bo'lsa o'zining foizini."""
    if MANAGE in user.permissions:
        return doctor_id
    if doctor_id and doctor_id != user.staff_id:
        raise HTTPException(403, "Boshqa shifokorning foizini ko'rish uchun ruxsat yo'q")
    return user.staff_id


def _parse_month(month: str):
    try:
        return commissions.month_bounds(month)
    except (ValueError, TypeError):
        raise HTTPException(422, "month YYYY-MM formatida bo'lishi kerak")


@router.get("/commissions/entries", tags=[TAG], response_model=List[EntryOut], summary="Foiz yozuvlari (oy bo'yicha)")
def list_entries(request: Request, month: str = Query(..., examples=["2026-11"]), doctor_id: Optional[uuid.UUID] = None,
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require("commissions:read"))):
    start, end = _parse_month(month)
    doctor_id = _scope_doctor(user, doctor_id)
    stmt = (select(CommissionEntry, Staff.full_name, Service.name, Invoice.number)
            .join(Staff, CommissionEntry.doctor_id == Staff.id).join(Service, CommissionEntry.service_id == Service.id)
            .join(Payment, CommissionEntry.payment_id == Payment.id).join(Invoice, Payment.invoice_id == Invoice.id)
            .where(CommissionEntry.entry_date >= start, CommissionEntry.entry_date < end)
            .order_by(CommissionEntry.entry_date, CommissionEntry.created_at))
    if doctor_id:
        stmt = stmt.where(CommissionEntry.doctor_id == doctor_id)
    rows = db.execute(stmt).all()
    audit.record_read(db, user, request, "commission", details={"month": month, "count": len(rows)})
    return [{"id": str(e.id), "kind": e.kind, "doctor_id": str(e.doctor_id), "doctor": doc, "service": svc, "invoice_number": num,
             "payment_id": str(e.payment_id), "refund_id": str(e.refund_id) if e.refund_id else None, "rule_kind": e.rule_kind,
             "rule_percent": e.rule_percent, "rule_fixed": e.rule_fixed, "base_amount": e.base_amount, "amount": e.amount,
             "entry_date": e.entry_date, "settled": e.settlement_id is not None} for e, doc, svc, num in rows]


@router.get("/commissions/report", tags=[TAG], response_model=MonthReport, summary="Oylik hisob (shifokorlar bo'yicha)",
            description="Hisoblangan (accrual), qaytarilgan (reversal) va sof foiz. Qaytarish keyingi oyda bo'lsa o'sha oyning manfiy yozuvi.")
def month_report(request: Request, month: str = Query(..., examples=["2026-11"]), doctor_id: Optional[uuid.UUID] = None,
                 db: Session = Depends(get_db), user: CurrentUser = Depends(require("commissions:read"))):
    start, end = _parse_month(month)
    doctor_id = _scope_doctor(user, doctor_id)
    stmt = (select(CommissionEntry.doctor_id, Staff.full_name, CommissionEntry.kind, func.sum(CommissionEntry.amount), func.count(),
                   func.bool_and(CommissionEntry.settlement_id.is_not(None)), func.min(CommissionEntry.settlement_id.cast(String)))
            .join(Staff, CommissionEntry.doctor_id == Staff.id)
            .where(CommissionEntry.entry_date >= start, CommissionEntry.entry_date < end)
            .group_by(CommissionEntry.doctor_id, Staff.full_name, CommissionEntry.kind))
    if doctor_id:
        stmt = stmt.where(CommissionEntry.doctor_id == doctor_id)
    docs: dict = {}
    for did, name, kind, total, n, settled, sid in db.execute(stmt).all():
        d = docs.setdefault(did, {"doctor_id": str(did), "doctor": name, "accrued": q2(0), "reversed": q2(0), "entries": 0, "settled": True,
                                  "settlement_id": None})
        if kind == CommissionEntryKind.accrual:
            d["accrued"] += q2(total)
        else:
            d["reversed"] += -q2(total)
        d["entries"] += n
        d["settled"] = d["settled"] and bool(settled)
        d["settlement_id"] = d["settlement_id"] or sid
    out = []
    for d in sorted(docs.values(), key=lambda x: x["doctor"]):
        d["net"] = d["accrued"] - d["reversed"]
        out.append(DoctorTotals(**d))
    audit.record_read(db, user, request, "commission", details={"month": month, "report": True})
    return {"month": month, "doctors": out, "total_net": sum((d.net for d in out), q2(0))}


@router.post("/commissions/settle", tags=[TAG], response_model=SettlementOut, status_code=201, summary="Oylik hisob-kitobni yopish",
             description="Shifokorning shu oydagi hamma yozuvlari yopiladi (qotadi), jami summa qayd etiladi. Bir oy bir shifokor uchun bir marta "
                         "yopiladi; keyingi qaytarishlar keyingi oyning manfiy yozuvi bo'ladi. Joriy yoki o'tgan oy.")
def settle(data: SettleIn, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require(MANAGE))):
    start, end = _parse_month(data.month)
    today = clinic_today()
    if start > today:
        raise HTTPException(422, "Kelajak oyni yopib bo'lmaydi")
    doctor = db.get(Staff, data.doctor_id)
    if not doctor or doctor.role != StaffRole.doctor:
        raise HTTPException(422, "Shifokor topilmadi")
    if db.scalar(select(CommissionSettlement.id).where(CommissionSettlement.doctor_id == doctor.id, CommissionSettlement.month == start)):
        raise HTTPException(409, "Bu oy shu shifokor uchun allaqachon yopilgan")
    entries = db.scalars(select(CommissionEntry).where(CommissionEntry.doctor_id == doctor.id, CommissionEntry.settlement_id.is_(None),
                                                       CommissionEntry.entry_date >= start, CommissionEntry.entry_date < end)
                         .with_for_update()).all()
    if not entries:
        raise HTTPException(409, "Yopiladigan foiz yozuvi yo'q")
    total = q2(sum((e.amount for e in entries), q2(0)))
    s = CommissionSettlement(doctor_id=doctor.id, month=start, amount=total, entries_count=len(entries), branch_id=user.branch_id,
                             created_by=user.id)
    db.add(s)
    db.flush()
    for e in entries:
        e.settlement_id = s.id
    audit.record(db, user, request, "create", "commission_settlement", s.id, {"doctor": doctor.full_name, "month": data.month,
                                                                                "amount": str(total), "entries": len(entries),
                                                                                "at": datetime.now(UTC).isoformat()})
    db.commit()
    return {"id": str(s.id), "doctor_id": str(doctor.id), "doctor": doctor.full_name, "month": data.month, "amount": total,
            "entries_count": len(entries)}


@router.get("/commissions/settlements", tags=[TAG], response_model=List[SettlementOut], summary="Yopilgan oylar")
def list_settlements(doctor_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("commissions:read"))):
    doctor_id = _scope_doctor(user, doctor_id)
    stmt = select(CommissionSettlement, Staff.full_name).join(Staff, CommissionSettlement.doctor_id == Staff.id).order_by(
        CommissionSettlement.month.desc())
    if doctor_id:
        stmt = stmt.where(CommissionSettlement.doctor_id == doctor_id)
    return [{"id": str(s.id), "doctor_id": str(s.doctor_id), "doctor": n, "month": s.month.strftime("%Y-%m"), "amount": s.amount,
             "entries_count": s.entries_count} for s, n in db.execute(stmt).all()]


