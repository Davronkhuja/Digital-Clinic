# ruff: noqa: E501
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import CashShift, ClinicSettings
from app.models.cash_shift import z_number_seq
from app.schemas.enums import CashShiftStatus
from app.schemas.shifts import ShiftClose, ShiftOpen, ShiftReport
from app.services import audit, pdf, shifts
from app.services.money import q2

router = APIRouter()
TAG = "🏦 Cash shifts"
ALL_SHIFTS = "finance:shifts"


def _get(db: Session, shift_id: uuid.UUID, user: CurrentUser) -> CashShift:
    s = db.get(CashShift, shift_id)
    if not s or (s.opened_by != user.id and ALL_SHIFTS not in user.permissions):
        raise HTTPException(404, "Smena topilmadi")
    return s


@router.post("/cash-shifts/open", tags=[TAG], response_model=ShiftReport, status_code=201, summary="Smenani ochish",
             description="Bitta kassirda bir vaqtda bitta ochiq smena. Naqd/karta to'lovi va qaytarish faqat ochiq smena bilan.")
def open_shift(data: ShiftOpen, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:write"))):
    shift = CashShift(opened_by=user.id, opened_at=datetime.now(UTC), opening_cash=q2(data.opening_cash), notes=data.notes,
                      branch_id=user.branch_id, created_by=user.id)
    db.add(shift)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Sizda ochiq smena allaqachon bor")
    audit.record(db, user, request, "create", "cash_shift", shift.id, {"opening_cash": str(shift.opening_cash)})
    db.commit()
    return shifts.report(db, shift)


@router.get("/cash-shifts/current", tags=[TAG], response_model=Optional[ShiftReport], summary="Mening ochiq smenam (X-hisobot) yoki null")
def current_shift(db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:write"))):
    shift = shifts.open_shift_of(db, user.id)
    return shifts.report(db, shift) if shift else None


@router.get("/cash-shifts", tags=[TAG], response_model=List[ShiftReport], summary="Smenalar (o'zimniki; `finance:shifts` bilan hammasi)")
def list_shifts(limit: int = 30, db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:read"))):
    stmt = select(CashShift).order_by(CashShift.opened_at.desc()).limit(max(1, min(limit, 200)))
    if ALL_SHIFTS not in user.permissions:
        stmt = stmt.where(CashShift.opened_by == user.id)
    return [shifts.report(db, s) for s in db.scalars(stmt)]


@router.get("/cash-shifts/{shift_id}/report", tags=[TAG], response_model=ShiftReport,
            summary="Smena hisoboti: ochiq bo'lsa X (joriy), yopilgan bo'lsa Z")
def shift_report(shift_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:read"))):
    s = _get(db, shift_id, user)
    audit.record_read(db, user, request, "cash_shift", s.id, {"report": True})
    return shifts.report(db, s)


@router.post("/cash-shifts/{shift_id}/close", tags=[TAG], response_model=ShiftReport, summary="Smenani yopish (Z-hisobot)",
             description="Sanalgan naqd kutilgan bilan solishtiriladi (kutilgan = boshlang'ich + naqd to'lovlar - naqd qaytarishlar). "
                         "Z-raqam beriladi, hisobot qotadi. Boshqa kassir smenasini faqat `finance:shifts`.")
def close_shift(shift_id: uuid.UUID, data: ShiftClose, request: Request, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("finance:write"))):
    s = _get(db, shift_id, user)
    if s.status != CashShiftStatus.open:
        raise HTTPException(409, "Smena allaqachon yopilgan")
    now = datetime.now(UTC)
    s.closed_at = now
    rep = shifts.report(db, s)
    counted = q2(data.counted_cash)
    s.status, s.closed_by, s.counted_cash = CashShiftStatus.closed, user.id, counted
    s.expected_cash, s.difference = rep["expected_cash"], q2(counted - rep["expected_cash"])
    s.z_number = f"Z-{db.scalar(select(z_number_seq.next_value())):06d}"
    if data.notes:
        s.notes = f"{s.notes}; {data.notes}" if s.notes else data.notes
    final = shifts.report(db, s)
    s.z_data = ShiftReport(**final).model_dump(mode="json")
    audit.record(db, user, request, "update", "cash_shift", s.id, {"closed": True, "z_number": s.z_number, "expected": str(s.expected_cash),
                                                                    "counted": str(counted), "difference": str(s.difference)})
    db.commit()
    return final


@router.get("/cash-shifts/{shift_id}/z-report/pdf", tags=[TAG], summary="Z-hisobot PDF", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def z_report_pdf(shift_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: CurrentUser = Depends(require("finance:read"))):
    s = _get(db, shift_id, user)
    clinic = db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == s.branch_id))
    content = pdf.z_report_pdf(ShiftReport(**shifts.report(db, s)).model_dump(mode="json"), {
        "name": clinic.clinic_name if clinic else None, "address": clinic.address if clinic else None, "phone": clinic.phone if clinic else None})
    audit.record_read(db, user, request, "cash_shift", s.id, {"pdf": True})
    return Response(content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="z-{str(s.id)[:8]}.pdf"'})
