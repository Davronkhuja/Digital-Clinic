# ruff: noqa: E501
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import (
    CashMovement,
    CommissionEntry,
    CommissionPayout,
    CommissionRule,
    CommissionSettlement,
    Invoice,
    Payment,
    Service,
    Staff,
    Transaction,
)
from app.schemas.commissions import DoctorTotals, EntryOut, MonthReport, PayIn, PayoutOut, RuleIn, RuleOut, SettleIn, SettlementOut
from app.schemas.enums import CashMovementKind, CommissionEntryKind, PayoutMethod, PayoutStatus, StaffRole, TransactionType
from app.services import audit, commissions, shifts
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
             "rule_percent": e.rule_percent, "rule_fixed": e.rule_fixed, "base_kind": e.base_kind, "base_amount": e.base_amount, "amount": e.amount,
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
    payout = None
    if total > 0:  # to'lanadigan summa bor: chiqim hujjati (Draft); manfiy/nol oyda hujjat yo'q
        payout = CommissionPayout(settlement_id=s.id, doctor_id=doctor.id, amount=total, branch_id=user.branch_id, created_by=user.id)
        db.add(payout)
        db.flush()
    audit.record(db, user, request, "create", "commission_settlement", s.id, {"doctor": doctor.full_name, "month": data.month,
                                                                                "amount": str(total), "entries": len(entries),
                                                                                "at": datetime.now(UTC).isoformat()})
    db.commit()
    return {"id": str(s.id), "doctor_id": str(doctor.id), "doctor": doctor.full_name, "month": data.month, "amount": total,
            "entries_count": len(entries), "payout_id": str(payout.id) if payout else None,
            "payout_status": payout.status if payout else None}


@router.get("/commissions/settlements", tags=[TAG], response_model=List[SettlementOut], summary="Yopilgan oylar")
def list_settlements(doctor_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("commissions:read"))):
    doctor_id = _scope_doctor(user, doctor_id)
    stmt = select(CommissionSettlement, Staff.full_name).join(Staff, CommissionSettlement.doctor_id == Staff.id).order_by(
        CommissionSettlement.month.desc())
    if doctor_id:
        stmt = stmt.where(CommissionSettlement.doctor_id == doctor_id)
    out = []
    for s, n in db.execute(stmt).all():
        payout = db.scalar(select(CommissionPayout).where(CommissionPayout.settlement_id == s.id))
        out.append({"id": str(s.id), "doctor_id": str(s.doctor_id), "doctor": n, "month": s.month.strftime("%Y-%m"), "amount": s.amount,
                    "entries_count": s.entries_count, "payout_id": str(payout.id) if payout else None,
                    "payout_status": payout.status if payout else None})
    return out




def _payout_out(db: Session, p: CommissionPayout) -> dict:
    s = db.get(CommissionSettlement, p.settlement_id)
    return {"id": str(p.id), "settlement_id": str(p.settlement_id), "doctor_id": str(p.doctor_id), "doctor": db.get(Staff, p.doctor_id).full_name,
            "month": s.month.strftime("%Y-%m"), "amount": p.amount, "status": p.status, "pay_method": p.pay_method, "reference": p.reference,
            "approved_by": shifts.cashier_name(db, p.approved_by), "approved_at": p.approved_at, "paid_by": shifts.cashier_name(db, p.paid_by),
            "paid_at": p.paid_at}


def _get_payout(db: Session, payout_id: uuid.UUID) -> CommissionPayout:
    p = db.scalar(select(CommissionPayout).where(CommissionPayout.id == payout_id).with_for_update())
    if not p:
        raise HTTPException(404, "To'lov hujjati topilmadi")
    return p


@router.get("/commission-payouts", tags=[TAG], response_model=List[PayoutOut], summary="Foiz to'lov hujjatlari (chiqim)",
            description="Oy yopilganda avtomatik yaratiladi (Draft) -> tasdiqlanadi (Approved) -> to'lanadi (Paid).")
def list_payouts(status: Optional[PayoutStatus] = None, doctor_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("commissions:read"))):
    doctor_id = _scope_doctor(user, doctor_id)
    stmt = select(CommissionPayout).order_by(CommissionPayout.created_at.desc())
    if status:
        stmt = stmt.where(CommissionPayout.status == status)
    if doctor_id:
        stmt = stmt.where(CommissionPayout.doctor_id == doctor_id)
    return [_payout_out(db, p) for p in db.scalars(stmt)]


@router.post("/commission-payouts/{payout_id}/approve", tags=[TAG], response_model=PayoutOut, summary="To'lov hujjatini tasdiqlash")
def approve_payout(payout_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require(MANAGE))):
    p = _get_payout(db, payout_id)
    if p.status != PayoutStatus.draft:
        raise HTTPException(409, "Faqat qoralama (Draft) hujjatni tasdiqlash mumkin")
    p.status, p.approved_by, p.approved_at = PayoutStatus.approved, user.id, datetime.now(UTC)
    audit.record(db, user, request, "update", "commission_payout", p.id, {"status": "Approved", "amount": str(p.amount)})
    db.commit()
    return _payout_out(db, p)


@router.post("/commission-payouts/{payout_id}/pay", tags=[TAG], response_model=PayoutOut, summary="To'lovni bajarish (naqd yoki o'tkazma)",
             description="`commissions:pay`; faqat tasdiqlangan hujjat. Naqd: to'lovchining ochiq kassa smenasiga chiqim bo'lib tushadi (kassadagi naqddan "
                         "oshmasligi kerak, Z-hisobotda alohida qator); ikkala usulda ham xarajat (`Shifokor foizi`) yoziladi.")
def pay_payout(payout_id: uuid.UUID, data: PayIn, request: Request, db: Session = Depends(get_db),
               user: CurrentUser = Depends(require("commissions:pay"))):
    p = _get_payout(db, payout_id)
    if p.status != PayoutStatus.approved:
        raise HTTPException(409, "Faqat tasdiqlangan (Approved) hujjatni to'lash mumkin")
    doctor = db.get(Staff, p.doctor_id)
    month = db.get(CommissionSettlement, p.settlement_id).month.strftime("%Y-%m")
    if data.method == PayoutMethod.cash:
        shift = shifts.require_open_shift(db, user.id)
        available = shifts.current_cash(db, shift)
        if p.amount > available:
            raise HTTPException(422, f"Kassadagi naqd yetarli emas (mavjud: {available})")
        db.add(CashMovement(shift_id=shift.id, kind=CashMovementKind.payout, amount=p.amount, counterparty=doctor.full_name,
                            note=f"Shifokor foizi {month}", payout_id=p.id, branch_id=shift.branch_id, created_by=user.id))
    p.status, p.paid_by, p.paid_at, p.pay_method, p.reference = PayoutStatus.paid, user.id, datetime.now(UTC), data.method, data.reference
    db.add(Transaction(type=TransactionType.expense, amount=p.amount, category="Shifokor foizi", date=clinic_today(),
                       description=f"Shifokor foizi {month}: {doctor.full_name} ({data.method.value})", payout_id=p.id,
                       branch_id=p.branch_id, created_by=user.id))
    audit.record(db, user, request, "pay", "commission_payout", p.id, {"amount": str(p.amount), "method": data.method.value, "doctor": doctor.full_name,
                                                                         "month": month})
    db.commit()
    return _payout_out(db, p)
