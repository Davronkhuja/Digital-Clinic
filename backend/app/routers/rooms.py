import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, require
from app.db.session import get_db
from app.models import Appointment, Room, Staff
from app.schemas import RoomIn, RoomOut, RoomUpdate

router = APIRouter()


def _out(r: Room) -> dict:
    return {"id": str(r.id), "name": r.name, "description": r.description, "is_active": r.is_active}


@router.get("/rooms", tags=["🚪 Rooms"], response_model=List[RoomOut], summary="Kabinetlar")
def get_rooms(include_inactive: bool = False, db: Session = Depends(get_db),
              user: CurrentUser = Depends(require("appointments:read"))):
    stmt = select(Room).where(Room.branch_id == user.branch_id).order_by(Room.name)
    if not include_inactive:
        stmt = stmt.where(Room.is_active.is_(True))
    return [_out(r) for r in db.scalars(stmt)]


@router.post("/rooms", tags=["🚪 Rooms"], response_model=RoomOut, status_code=201, summary="Kabinet qo'shish")
def create_room(data: RoomIn, db: Session = Depends(get_db), user: CurrentUser = Depends(require("settings:write"))):
    room = Room(name=data.name.strip(), description=data.description, is_active=data.is_active,
                branch_id=user.branch_id, created_by=user.id)
    db.add(room)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli kabinet allaqachon mavjud")
    return _out(room)


def _get_room(db: Session, room_id: uuid.UUID, user: CurrentUser) -> Room:
    room = db.get(Room, room_id)
    if not room or room.branch_id != user.branch_id:
        raise HTTPException(404, "Kabinet topilmadi")
    return room


@router.put("/rooms/{room_id}", tags=["🚪 Rooms"], response_model=RoomOut, summary="Kabinetni o'zgartirish")
def update_room(room_id: uuid.UUID, data: RoomUpdate, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("settings:write"))):
    room = _get_room(db, room_id, user)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(room, key, value.strip() if key == "name" else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bunday nomli kabinet allaqachon mavjud")
    return _out(room)


@router.delete("/rooms/{room_id}", tags=["🚪 Rooms"], summary="Kabinetni o'chirish",
               description="Qabullarda ishlatilgan kabinet o'chirilmaydi, faolsizlantiriladi.")
def delete_room(room_id: uuid.UUID, db: Session = Depends(get_db),
                user: CurrentUser = Depends(require("settings:write"))):
    room = _get_room(db, room_id, user)
    used = db.scalar(select(func.count()).select_from(Appointment).where(Appointment.room_id == room.id))
    if used:
        room.is_active = False
        db.execute(Staff.__table__.update().where(Staff.default_room_id == room.id).values(default_room_id=None))
        db.commit()
        return {"message": "Kabinet qabullarda ishlatilgan: faolsizlantirildi"}
    db.delete(room)  # shifokorlarning default_room_id i SET NULL
    db.commit()
    return {"message": "Kabinet o'chirildi"}
