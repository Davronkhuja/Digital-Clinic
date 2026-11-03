import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, load_current_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models import RefreshToken


def client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:300] or None
    return ip, ua


def issue_tokens(db: Session, user: CurrentUser, request: Request) -> dict:
    ip, ua = client_meta(request)
    refresh, jti, expires_at = create_refresh_token(user.id)
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at, ip=ip, user_agent=ua, created_by=user.id))
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user.public(),
    }


def revoke_all(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


def rotate_refresh(db: Session, token: str, request: Request) -> dict:
    """Refresh tokenni aylantiradi. Bekor qilingan token qayta ishlatilsa, butun oila bekor qilinadi."""
    payload = decode_token(token, "refresh")
    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == uuid.UUID(payload["jti"])))
    if not row:
        raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan")
    if row.revoked_at is not None:
        revoke_all(db, row.user_id)  # o'g'irlangan token ishlatilgan bo'lishi mumkin
        db.commit()
        raise HTTPException(401, "Token bekor qilingan")
    user = load_current_user(db, row.user_id)
    if not user:
        raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan")
    row.revoked_at = datetime.now(timezone.utc)
    return issue_tokens(db, user, request)


def revoke_refresh(db: Session, token: str, user_id: uuid.UUID) -> None:
    try:
        payload = decode_token(token, "refresh")
    except HTTPException:
        return  # yaroqsiz token allaqachon foydasiz
    row = db.scalar(select(RefreshToken).where(RefreshToken.jti == uuid.UUID(payload["jti"])))
    if row and row.user_id == user_id and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
