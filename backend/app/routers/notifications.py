import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.models import Notification, NotificationRead

router = APIRouter()
TAG = "🔔 Notifications (bildirishnomalar)"


class NotificationOut(BaseModel):
    id: str
    kind: str
    title: str
    body: Optional[str] = None
    link: Optional[str] = None
    created_at: str
    read: bool


class UnreadOut(BaseModel):
    unread: int


def _visible(user: CurrentUser):
    """Faol filial va foydalanuvchining ruxsatlari bo'yicha ko'rinadigan bildirishnomalar."""
    return (Notification.branch_id == user.branch_id) & Notification.permission.in_(list(user.permissions))


def _read_ids(db: Session, user: CurrentUser):
    return select(NotificationRead.notification_id).where(NotificationRead.user_id == user.id)


@router.get("/notifications", tags=[TAG], response_model=List[NotificationOut], summary="Mening bildirishnomalarim",
            description="Faol filial va ruxsatlarga mos (masalan ombor ogohlantirishlari `warehouse:write` bor xodimga). Yangilari tepada.")
def list_notifications(unread_only: bool = False, limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db),
                       user: CurrentUser = Depends(get_current_user)):
    read = set(db.scalars(_read_ids(db, user)))
    stmt = select(Notification).where(_visible(user)).order_by(Notification.created_at.desc(), Notification.id).limit(limit)
    if unread_only:
        stmt = stmt.where(Notification.id.not_in(_read_ids(db, user)))
    return [{"id": str(n.id), "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "created_at": n.created_at.isoformat(),
             "read": n.id in read} for n in db.scalars(stmt)]


@router.get("/notifications/unread-count", tags=[TAG], response_model=UnreadOut, summary="O'qilmagan bildirishnomalar soni")
def unread_count(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    n = db.scalar(select(func.count()).select_from(Notification).where(_visible(user), Notification.id.not_in(_read_ids(db, user))))
    return {"unread": n}


def _mark(db: Session, user: CurrentUser, ids: list[uuid.UUID]) -> None:
    if ids:
        db.execute(insert(NotificationRead).values([{"notification_id": i, "user_id": user.id} for i in ids])
                   .on_conflict_do_nothing(index_elements=["notification_id", "user_id"]))


@router.post("/notifications/{notification_id}/read", tags=[TAG], response_model=UnreadOut, summary="O'qilgan deb belgilash")
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    n = db.scalar(select(Notification).where(Notification.id == notification_id, _visible(user)))
    if not n:
        raise HTTPException(404, "Bildirishnoma topilmadi")
    _mark(db, user, [n.id])
    db.commit()
    return unread_count(db, user)


@router.post("/notifications/read-all", tags=[TAG], response_model=UnreadOut, summary="Hammasini o'qilgan deb belgilash")
def mark_all_read(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    ids = list(db.scalars(select(Notification.id).where(_visible(user), Notification.id.not_in(_read_ids(db, user)))))
    _mark(db, user, ids)
    db.commit()
    return unread_count(db, user)
