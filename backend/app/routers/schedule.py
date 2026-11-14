# ruff: noqa: E501
import uuid
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment, Branch, DoctorSchedule, ScheduleException, Staff, StaffBranch
from app.schemas import ExceptionIn, ExceptionOut, ScheduleOut, ScheduleTemplate, SlotsOut, StaffBranchesIn
from app.schemas.enums import AppointmentStatus, ExceptionKind, StaffRole
from app.services import audit, availability
from app.services.booking import resolve_room
from app.services.periods import CLINIC_TZ
from app.services.scheduling import resolve_duration

router = APIRouter()
TAG = "🗓 Schedule"


def _doctor(db: Session, staff_id: uuid.UUID) -> Staff:
    doctor = db.get(Staff, staff_id)
    if not doctor or doctor.role != StaffRole.doctor:
        raise HTTPException(404, "Shifokor topilmadi")
    return doctor


def _affected(db: Session, e: ScheduleException) -> list[str]:
    """Istisno davriga tushgan rejalashtirilgan qabullar (ish vaqtidan tashqarida qolganlar)."""
    appts = db.scalars(
        select(Appointment).where(
            Appointment.doctor_id == e.staff_id, Appointment.branch_id == e.branch_id, Appointment.status == AppointmentStatus.scheduled,
            Appointment.date >= e.date_from, Appointment.date <= e.date_to,
        )
    ).all()
    return [str(a.id) for a in appts
            if not any(ws <= a.starts_at and a.ends_at <= we for ws, we in availability.day_windows(db, e.staff_id, a.date, e.branch_id))]


def _exception_out(db: Session, e: ScheduleException, with_affected: bool = False) -> dict:
    return {
        "id": str(e.id), "kind": e.kind, "date_from": e.date_from, "date_to": e.date_to, "start_time": e.start_time,
        "end_time": e.end_time, "break_start": e.break_start, "break_end": e.break_end, "note": e.note,
        "affected_appointments": _affected(db, e) if with_affected else [],
    }


def _doctor_branches(db: Session, staff_id: uuid.UUID) -> list[dict]:
    home = db.scalar(select(Staff.branch_id).where(Staff.id == staff_id))
    rows = db.execute(select(Branch).join(StaffBranch, StaffBranch.branch_id == Branch.id).where(StaffBranch.staff_id == staff_id)
                      .order_by(Branch.is_default.desc(), Branch.name)).scalars()
    return [{"id": str(b.id), "name": b.name, "home": b.id == home} for b in rows]


def _schedule_out(db: Session, staff_id: uuid.UUID, branch_id: uuid.UUID) -> dict:
    days = db.scalars(select(DoctorSchedule).where(DoctorSchedule.staff_id == staff_id, DoctorSchedule.branch_id == branch_id)
                      .order_by(DoctorSchedule.weekday)).all()
    excs = db.scalars(select(ScheduleException).where(ScheduleException.staff_id == staff_id, ScheduleException.branch_id == branch_id)
                      .order_by(ScheduleException.date_from)).all()
    return {
        "staff_id": str(staff_id), "branch_id": str(branch_id), "branches": _doctor_branches(db, staff_id),
        "days": [{"weekday": d.weekday, "start_time": d.start_time, "end_time": d.end_time,
                  "break_start": d.break_start, "break_end": d.break_end} for d in days],
        "exceptions": [_exception_out(db, e) for e in excs],
    }


WEEKDAYS = ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"]
CROSS = "Shifokor shu vaqtda boshqa filialda ishlaydi ({branch}, {when}): bir vaqtda ikki filialda jadval bo'lishi mumkin emas"


def _require_member(db: Session, staff_id: uuid.UUID, branch_id: uuid.UUID) -> None:
    if not availability.works_in_branch(db, staff_id, branch_id):
        raise HTTPException(422, "Shifokor bu filialda ishlamaydi: avval filialga biriktiring (PUT /staff/{id}/branches)")


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def _check_template_cross_branch(db: Session, staff_id: uuid.UUID, branch_id: uuid.UUID, days) -> None:
    other = db.execute(select(DoctorSchedule, Branch.name).join(Branch, DoctorSchedule.branch_id == Branch.id)
                       .where(DoctorSchedule.staff_id == staff_id, DoctorSchedule.branch_id != branch_id)).all()
    for d in days:
        for row, name in other:
            if row.weekday == d.weekday and _overlaps(d.start_time, d.end_time, row.start_time, row.end_time):
                raise HTTPException(409, CROSS.format(branch=name, when=f"{WEEKDAYS[d.weekday]} {row.start_time:%H:%M}-{row.end_time:%H:%M}"))


@router.get("/staff/{staff_id}/schedule", tags=[TAG], response_model=ScheduleOut,
            summary="Shifokorning faol filialdagi haftalik shabloni va istisnolari",
            description="Jadval filial bo'yicha: faol filialniki (`X-Branch-Id`) ko'rsatiladi; `branches`: shifokor ishlaydigan filiallar.")
def get_schedule(staff_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("staff:read"))):
    _doctor(db, staff_id)
    return _schedule_out(db, staff_id, user.branch_id)


@router.put("/staff/{staff_id}/schedule", tags=[TAG], response_model=ScheduleOut,
            summary="Faol filialdagi haftalik shablonni almashtirish",
            description="Ro'yxatda yo'q kunlar dam olish kuni. Bo'sh ro'yxat: shu filialda shablon yo'q. Boshqa filialdagi shablonlar o'zgarmaydi; "
                        "bir hafta kunida ikki filial oynalari kesishsa 409. Mavjud qabullar o'zgarmaydi.")
def put_schedule(staff_id: uuid.UUID, data: ScheduleTemplate, request: Request, db: Session = Depends(get_db),
                 user: CurrentUser = Depends(require("staff:write"))):
    _doctor(db, staff_id)
    _require_member(db, staff_id, user.branch_id)
    _check_template_cross_branch(db, staff_id, user.branch_id, data.days)
    db.execute(delete(DoctorSchedule).where(DoctorSchedule.staff_id == staff_id, DoctorSchedule.branch_id == user.branch_id))
    for d in data.days:
        db.add(DoctorSchedule(staff_id=staff_id, branch_id=user.branch_id, weekday=d.weekday, start_time=d.start_time, end_time=d.end_time,
                              break_start=d.break_start, break_end=d.break_end, created_by=user.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Shifokor boshqa filialda shu vaqtda ishlaydi: bir vaqtda ikki filialda jadval bo'lishi mumkin emas")
    audit.record(db, user, request, "update", "doctor_schedule", staff_id, {"branch_id": str(user.branch_id), "days": len(data.days)})
    db.commit()
    return _schedule_out(db, staff_id, user.branch_id)


def _check_extra_cross_branch(db: Session, staff_id: uuid.UUID, branch_id: uuid.UUID, data: ExceptionIn) -> None:
    """Qo'shimcha ish kuni boshqa filialdagi (o'sha kungi samarali) ish oynalari bilan kesishmasin."""
    day = data.date_from
    start, end = availability._at(day, data.start_time), availability._at(day, data.end_time)
    for b in db.execute(select(Branch).join(StaffBranch, StaffBranch.branch_id == Branch.id)
                        .where(StaffBranch.staff_id == staff_id, Branch.id != branch_id)).scalars():
        for ws, we in availability.day_windows(db, staff_id, day, b.id):
            if _overlaps(start, end, ws, we) and (we - ws) < timedelta(hours=23):      # cheklovsiz (butun kun) emas, haqiqiy jadval
                raise HTTPException(409, CROSS.format(branch=b.name, when=f"{day} {ws:%H:%M}-{we:%H:%M}"))


@router.post("/staff/{staff_id}/schedule/exceptions", tags=[TAG], response_model=ExceptionOut, status_code=201,
             summary="Istisno qo'shish (ta'til, kasallik, dam olish, qo'shimcha ish kuni): faol filial uchun",
             description="Javobdagi `affected_appointments`: shu davrda ish vaqtidan tashqarida qolgan rejalashtirilgan qabullar "
                         "(avtomatik bekor qilinmaydi, ko'chirish kerak). `all_branches=true` (ta'til/kasallik/dam olish): shifokor ishlaydigan "
                         "hamma filialga. Qo'shimcha ish kuni boshqa filialdagi ish oynasi bilan kesishsa 409.")
def add_exception(staff_id: uuid.UUID, data: ExceptionIn, request: Request, db: Session = Depends(get_db),
                  user: CurrentUser = Depends(require("staff:write"))):
    _doctor(db, staff_id)
    _require_member(db, staff_id, user.branch_id)
    if data.kind == ExceptionKind.extra_work:
        _check_extra_cross_branch(db, staff_id, user.branch_id, data)
    branches = ([uuid.UUID(b["id"]) for b in _doctor_branches(db, staff_id)] if data.all_branches else [user.branch_id])
    created = []
    for bid in branches:
        e = ScheduleException(staff_id=staff_id, branch_id=bid, kind=data.kind, date_from=data.date_from, date_to=data.date_to or data.date_from,
                              start_time=data.start_time, end_time=data.end_time, break_start=data.break_start, break_end=data.break_end,
                              note=data.note, created_by=user.id)
        db.add(e)
        created.append(e)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Shifokor boshqa filialda shu vaqtda ishlaydi: bir vaqtda ikki filialda jadval bo'lishi mumkin emas")
    audit.record(db, user, request, "create", "schedule_exception", created[0].id,
                 {"staff_id": str(staff_id), "kind": data.kind.value, "branches": [str(b) for b in branches]})
    db.commit()
    mine = next(e for e in created if e.branch_id == user.branch_id)
    return _exception_out(db, mine, with_affected=mine.kind != ExceptionKind.extra_work)


@router.delete("/staff/{staff_id}/schedule/exceptions/{exception_id}", tags=[TAG], summary="Istisnoni olib tashlash (faol filialniki)")
def delete_exception(staff_id: uuid.UUID, exception_id: uuid.UUID, db: Session = Depends(get_db),
                     user: CurrentUser = Depends(require("staff:write"))):
    e = db.get(ScheduleException, exception_id)
    if not e or e.staff_id != staff_id or e.branch_id != user.branch_id:
        raise HTTPException(404, "Istisno topilmadi")
    db.delete(e)
    db.commit()
    return {"message": "Istisno olib tashlandi"}


@router.get("/staff/{staff_id}/branches", tags=[TAG], response_model=list, summary="Shifokor ishlaydigan filiallar")
def get_staff_branches(staff_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(require("staff:read"))):
    if not db.get(Staff, staff_id):
        raise HTTPException(404, "Xodim topilmadi")
    return _doctor_branches(db, staff_id)


@router.put("/staff/{staff_id}/branches", tags=[TAG], response_model=list, summary="Shifokor ishlaydigan filiallarni belgilash",
            description="`branches:manage`. Asosiy filial doim kiradi. Olib tashlangan filialda rejalashtirilgan qabul bo'lsa 409; "
                        "olib tashlangan filialdagi jadval shabloni va istisnolari o'chiriladi.")
def put_staff_branches(staff_id: uuid.UUID, data: StaffBranchesIn, request: Request, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("branches:manage"))):
    staff = db.get(Staff, staff_id)
    if not staff:
        raise HTTPException(404, "Xodim topilmadi")
    try:
        wanted = {uuid.UUID(b) for b in data.branch_ids} | {staff.branch_id}
    except ValueError:
        raise HTTPException(422, "branch_ids noto'g'ri")
    active = set(db.scalars(select(Branch.id).where(Branch.id.in_(wanted), Branch.is_active.is_(True))))
    if wanted - active:
        raise HTTPException(422, "Filial topilmadi yoki faol emas")
    current = set(db.scalars(select(StaffBranch.branch_id).where(StaffBranch.staff_id == staff_id)))
    for bid in current - wanted:
        if db.scalar(select(Appointment.id).where(Appointment.doctor_id == staff_id, Appointment.branch_id == bid,
                                                  Appointment.status == AppointmentStatus.scheduled,
                                                  Appointment.starts_at > datetime.now(CLINIC_TZ)).limit(1)):
            raise HTTPException(409, "Bu filialda rejalashtirilgan qabullar bor: avval ularni ko'chiring yoki bekor qiling")
        db.execute(delete(DoctorSchedule).where(DoctorSchedule.staff_id == staff_id, DoctorSchedule.branch_id == bid))
        db.execute(delete(ScheduleException).where(ScheduleException.staff_id == staff_id, ScheduleException.branch_id == bid))
        db.execute(delete(StaffBranch).where(StaffBranch.staff_id == staff_id, StaffBranch.branch_id == bid))
    for bid in wanted - current:
        db.add(StaffBranch(staff_id=staff_id, branch_id=bid, created_by=user.id))
    audit.record(db, user, request, "update", "staff_branches", staff_id, {"branches": sorted(str(b) for b in wanted)})
    db.commit()
    return _doctor_branches(db, staff_id)


@router.get("/staff/{staff_id}/slots", tags=[TAG], response_model=SlotsOut, summary="Bo'sh qabul vaqtlari",
            description="Ish oynalari (shablon + istisnolar) ichida, shifokor va kabinet band bo'lmagan boshlanish vaqtlari. "
                        "Davomiylik: `duration_min` -> `type` -> shifokor standarti. Bugun uchun o'tgan vaqtlar chiqmaydi.")
def get_slots(
    staff_id: uuid.UUID,
    date: date_type = Query(..., description="Klinika sanasi (YYYY-MM-DD)"),
    type: Optional[str] = Query(None, description="Qabul turi (davomiylik uchun)"),
    duration_min: Optional[int] = Query(None, ge=5, le=480),
    step_min: int = Query(15, ge=5, le=120, description="Boshlanish vaqtlari qadami"),
    room_id: Optional[uuid.UUID] = Query(None, description="Bo'lmasa: shifokorning standart kabineti"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("appointments:read")),
):
    doctor = _doctor(db, staff_id)
    duration = resolve_duration(db, doctor, type or "", duration_min)
    room = resolve_room(db, room_id, doctor, user.branch_id)
    slots = availability.free_slots(db, doctor, date, duration, step_min, room.id if room else None,
                                    now=datetime.now(CLINIC_TZ), branch_id=user.branch_id)
    return {
        "date": date.isoformat(), "doctor_id": str(doctor.id), "duration_min": duration,
        "room_id": str(room.id) if room else None,
        "slots": [{"time": s.astimezone(CLINIC_TZ).strftime("%H:%M"), "end_time": e.astimezone(CLINIC_TZ).strftime("%H:%M")}
                  for s, e in slots],
    }

