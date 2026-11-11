import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment, AppointmentType, Staff
from app.schemas import Appointment as AppointmentOut
from app.schemas import (
    AppointmentCreate,
    AppointmentStatus,
    AppointmentTypeIn,
    AppointmentTypeOut,
    AppointmentTypeUpdate,
    AppointmentUpdate,
)
from app.services import queries
from app.services.booking import commit_booking, resolve_room
from app.services.lookup import get_patient_or_404, resolve_doctor
from app.services.periods import CLINIC_TZ
from app.services.scheduling import appointment_window, resolve_duration

router = APIRouter()


@router.get("/appointments", tags=["📅 Appointments"], response_model=List[AppointmentOut],
            summary="Uchrashuvlar ro'yxati")
def get_appointments(
    date: Optional[str] = Query(None, description="Sana bo'yicha filter (YYYY-MM-DD)"),
    doctor: Optional[str] = Query(None, description="Shifokor bo'yicha filter"),
    status: Optional[AppointmentStatus] = Query(None, description="Status bo'yicha filter"),
    patient_id: Optional[uuid.UUID] = Query(None, description="Bemor ID bo'yicha filter"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("appointments:read")),
):
    try:
        return queries.list_appointments(db, date, doctor, status, patient_id)
    except ValueError:
        raise HTTPException(422, "date YYYY-MM-DD formatida bo'lishi kerak")


@router.post("/appointments", tags=["📅 Appointments"], response_model=AppointmentOut, status_code=201,
             summary="Uchrashuv rejalashtirish")
def create_appointment(data: AppointmentCreate, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    patient = get_patient_or_404(db, data.patient_id)
    doctor = resolve_doctor(db, data.doctor_id, data.doctor)
    duration = resolve_duration(db, doctor, data.type, data.duration_min)
    try:
        starts_at, ends_at = appointment_window(data.date, data.time, duration)
    except ValueError:
        raise HTTPException(422, "Sana yoki vaqt noto'g'ri")
    room = resolve_room(db, data.room_id, doctor)
    appt = Appointment(
        patient_id=patient.id, doctor_id=doctor.id, room_id=room.id if room else None, starts_at=starts_at,
        ends_at=ends_at, type=data.type, notes=data.notes, branch_id=user.branch_id, created_by=user.id,
    )
    db.add(appt)
    commit_booking(db)
    return queries.list_appointments(db, appt_id=appt.id)[0]


@router.patch("/appointments/{appt_id}/status", tags=["📅 Appointments"], response_model=AppointmentOut,
              summary="Uchrashuv statusini o'zgartirish")
def update_appointment_status(appt_id: uuid.UUID, status: AppointmentStatus, db: Session = Depends(get_db),
                              user: CurrentUser = Depends(require("appointments:write"))):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Uchrashuv topilmadi")
    appt.status = status
    commit_booking(db)  # bekor qilingan qabulni qayta faollashtirish band vaqtga to'qnashishi mumkin
    return queries.list_appointments(db, appt_id=appt_id)[0]


@router.patch("/appointments/{appt_id}", tags=["📅 Appointments"], response_model=AppointmentOut,
              summary="Uchrashuvni ko'chirish yoki o'zgartirish",
              description="Faqat `Scheduled` uchrashuv. Vaqt, shifokor yoki kabinet band bo'lsa 409.")
def update_appointment(appt_id: uuid.UUID, data: AppointmentUpdate, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Uchrashuv topilmadi")
    if appt.status != AppointmentStatus.scheduled:
        raise HTTPException(409, "Faqat rejalashtirilgan (Scheduled) uchrashuvni o'zgartirish mumkin")
    fields = data.model_dump(exclude_unset=True)
    if fields.get("doctor_id") or fields.get("doctor"):
        appt.doctor_id = resolve_doctor(db, fields.get("doctor_id"), fields.get("doctor")).id
    doctor = db.get(Staff, appt.doctor_id)
    if fields.get("type"):
        appt.type = fields["type"]
    if "notes" in fields:
        appt.notes = fields["notes"]
    if "room_id" in fields:  # null: kabinetsiz; qiymat: aniq kabinet
        room = resolve_room(db, fields["room_id"], doctor) if fields["room_id"] else None
        appt.room_id = room.id if room else None
    elif fields.get("doctor_id") or fields.get("doctor"):  # shifokor almashdi: yangi shifokorning standart kabineti
        room = resolve_room(db, None, doctor)
        appt.room_id = room.id if room else None
    if {"date", "time", "duration_min", "type"} & fields.keys():
        local = appt.starts_at.astimezone(CLINIC_TZ)
        duration = fields.get("duration_min") or (
            resolve_duration(db, doctor, appt.type) if "type" in fields else appt.duration_min)
        try:
            appt.starts_at, appt.ends_at = appointment_window(
                fields.get("date") or local.date().isoformat(), fields.get("time") or local.strftime("%H:%M"), duration)
        except ValueError:
            raise HTTPException(422, "Sana yoki vaqt noto'g'ri")
    commit_booking(db)
    return queries.list_appointments(db, appt_id=appt_id)[0]


@router.delete("/appointments/{appt_id}", tags=["📅 Appointments"], summary="Uchrashuvni bekor qilish")
def delete_appointment(appt_id: uuid.UUID, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("appointments:write"))):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Uchrashuv topilmadi")
    db.delete(appt)
    db.commit()
    return {"message": "Uchrashuv bekor qilindi"}


def _type_out(t: AppointmentType) -> dict:
    return {"id": str(t.id), "name": t.name, "duration_min": t.duration_min, "is_active": t.is_active}


@router.get("/appointment-types", tags=["📅 Appointments"], response_model=List[AppointmentTypeOut],
            summary="Qabul turlari va davomiyligi")
def get_appointment_types(include_inactive: bool = False, db: Session = Depends(get_db),
                          user: CurrentUser = Depends(require("appointments:read"))):
    stmt = select(AppointmentType).order_by(AppointmentType.name)
    if not include_inactive:
        stmt = stmt.where(AppointmentType.is_active.is_(True))
    return [_type_out(t) for t in db.scalars(stmt)]


@router.post("/appointment-types", tags=["📅 Appointments"], response_model=AppointmentTypeOut, status_code=201,
             summary="Qabul turi qo'shish")
def create_appointment_type(data: AppointmentTypeIn, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(require("settings:write"))):
    t = AppointmentType(name=data.name.strip(), duration_min=data.duration_min, is_active=data.is_active,
                        created_by=user.id)
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday qabul turi allaqachon mavjud")
    return _type_out(t)


@router.put("/appointment-types/{type_id}", tags=["📅 Appointments"], response_model=AppointmentTypeOut,
            summary="Qabul turini o'zgartirish", description="Mavjud uchrashuvlar davomiyligi o'zgarmaydi.")
def update_appointment_type(type_id: uuid.UUID, data: AppointmentTypeUpdate, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(require("settings:write"))):
    t = db.get(AppointmentType, type_id)
    if not t:
        raise HTTPException(404, "Qabul turi topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(t, key, value.strip() if key == "name" else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday qabul turi allaqachon mavjud")
    return _type_out(t)


@router.delete("/appointment-types/{type_id}", tags=["📅 Appointments"], summary="Qabul turini o'chirish",
               description="Uchrashuvlar turni nom bilan saqlaydi, shuning uchun tur faolsizlantiriladi.")
def delete_appointment_type(type_id: uuid.UUID, db: Session = Depends(get_db),
                            user: CurrentUser = Depends(require("settings:write"))):
    t = db.get(AppointmentType, type_id)
    if not t:
        raise HTTPException(404, "Qabul turi topilmadi")
    in_use = db.scalar(select(func.count()).select_from(Appointment).where(func.lower(Appointment.type) == t.name.lower()))
    if in_use:
        t.is_active = False
        db.commit()
        return {"message": "Tur uchrashuvlarda ishlatilgan: faolsizlantirildi"}
    db.delete(t)
    db.commit()
    return {"message": "Qabul turi o'chirildi"}
