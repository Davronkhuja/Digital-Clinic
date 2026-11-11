"""Qabul yozish: kabinetni aniqlash va band vaqt cheklovini (bazadagi exclusion) 409 ga aylantirish."""
import uuid

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Room, Staff

BUSY_MESSAGES = {
    "no_doctor_overlap": "Shifokor bu vaqtda band: boshqa qabul bilan kesishadi",
    "no_room_overlap": "Kabinet bu vaqtda band: boshqa qabul bilan kesishadi",
}


def resolve_room(db: Session, room_id: uuid.UUID | None, doctor: Staff) -> Room | None:
    """Aniq ko'rsatilgan kabinet (faol, shifokor filialida bo'lishi shart), bo'lmasa shifokorning standart kabineti."""
    if room_id:
        room = db.get(Room, room_id)
        if not room or not room.is_active:
            raise HTTPException(422, "Kabinet topilmadi yoki faol emas")
        if room.branch_id != doctor.branch_id:
            raise HTTPException(422, "Kabinet shifokor filialiga tegishli emas")
        return room
    if doctor.default_room_id:
        room = db.get(Room, doctor.default_room_id)
        return room if room and room.is_active else None
    return None


def commit_booking(db: Session) -> None:
    """commit; band vaqt bo'lsa 409 (poyga holatida ham: cheklov bazada)."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if name in BUSY_MESSAGES:
            raise HTTPException(409, BUSY_MESSAGES[name])
        raise
