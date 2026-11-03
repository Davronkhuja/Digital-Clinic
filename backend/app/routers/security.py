import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, require
from app.db.session import get_db
from app.models import AuditLog, RefreshToken, Staff, User
from app.schemas import AuditPage, SessionOut
from app.services import audit

router = APIRouter()


@router.get("/security/audit", tags=["🔒 Security"], response_model=AuditPage, summary="Audit jurnali",
            description="Bemor, EMR va to'lov yozuvlarini o'qish/yozish va kirish hodisalari: kim, qachon, nima, IP.")
def get_audit(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require("audit:read")),
):
    stmt = (
        select(AuditLog, Staff.full_name)
        .outerjoin(User, AuditLog.user_id == User.id)
        .outerjoin(Staff, User.staff_id == Staff.id)
    )
    count = select(func.count()).select_from(AuditLog)
    for column, value in ((AuditLog.action, action), (AuditLog.entity_type, entity_type), (AuditLog.user_id, user_id)):
        if value:
            stmt, count = stmt.where(column == value), count.where(column == value)
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id).offset(skip).limit(limit)).all()
    items = [
        {"id": str(a.id), "created_at": a.created_at.isoformat(), "user_id": str(a.user_id) if a.user_id else None,
         "user_name": name, "action": a.action, "entity_type": a.entity_type,
         "entity_id": str(a.entity_id) if a.entity_id else None, "ip": a.ip, "details": a.details}
        for a, name in rows
    ]
    return {"items": items, "total": db.scalar(count)}


def _sessions(db: Session, user_id: uuid.UUID | None) -> list[dict]:
    stmt = (
        select(RefreshToken, User.email, Staff.full_name)
        .join(User, RefreshToken.user_id == User.id)
        .join(Staff, User.staff_id == Staff.id)
        .where(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > datetime.now(UTC))
        .order_by(RefreshToken.created_at.desc())
    )
    if user_id:
        stmt = stmt.where(RefreshToken.user_id == user_id)
    return [
        {"id": str(t.id), "user_id": str(t.user_id), "user_name": name, "email": email, "ip": t.ip,
         "user_agent": t.user_agent, "last_active": t.created_at.isoformat(), "expires_at": t.expires_at.isoformat()}
        for t, email, name in db.execute(stmt).all()
    ]


@router.get("/security/sessions", tags=["🔒 Security"], response_model=List[SessionOut],
            summary="Barcha faol sessiyalar (administrator)")
def all_sessions(db: Session = Depends(get_db), user: CurrentUser = Depends(require("audit:read"))):
    return _sessions(db, None)


@router.get("/auth/sessions", tags=["🔐 Auth"], response_model=List[SessionOut], summary="Mening faol sessiyalarim")
def my_sessions(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    return _sessions(db, user.id)


def _revoke(db: Session, request: Request, actor: CurrentUser, session_id: uuid.UUID, only_own: bool) -> dict:
    token = db.get(RefreshToken, session_id)
    if not token or token.revoked_at is not None or (only_own and token.user_id != actor.id):
        raise HTTPException(404, "Sessiya topilmadi")
    token.revoked_at = datetime.now(UTC)
    audit.record(db, actor, request, "revoke_session", "session", token.id, {"user_id": str(token.user_id)})
    db.commit()
    return {"message": "Sessiya bekor qilindi"}


@router.delete("/auth/sessions/{session_id}", tags=["🔐 Auth"], summary="O'z sessiyamni bekor qilish")
def revoke_my_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    return _revoke(db, request, user, session_id, only_own=True)


@router.delete("/security/sessions/{session_id}", tags=["🔒 Security"],
               summary="Istalgan sessiyani bekor qilish (administrator)",
               description="Refresh token bekor qilinadi; amaldagi access token muddati tugaguncha (<=30 daqiqa) ishlashi mumkin.")
def revoke_any_session(session_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                       user: CurrentUser = Depends(require("roles:manage"))):
    return _revoke(db, request, user, session_id, only_own=False)
