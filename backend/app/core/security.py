import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import HTTPException

from app.core.config import settings

UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def hash_password(password: str) -> str:
    # bcrypt faqat birinchi 72 baytni hisobga oladi
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, uuid.UUID, datetime]:
    """(token, jti, expires_at). jti bazada saqlanadi va bekor qilinishi mumkin."""
    now = datetime.now(UTC)
    jti = uuid.uuid4()
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "jti": str(jti), "type": "refresh", "iat": now, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), jti, expires_at


def decode_token(token: str, expected_type: str) -> dict:
    """Tokenni tekshiradi; yaroqsiz, eskirgan yoki turi noto'g'ri bo'lsa 401."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError:
        raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan", headers=UNAUTHORIZED_HEADERS)
    if payload.get("type") != expected_type:
        raise HTTPException(401, "Token turi noto'g'ri", headers=UNAUTHORIZED_HEADERS)
    try:
        uuid.UUID(payload["sub"])
    except ValueError:
        raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan", headers=UNAUTHORIZED_HEADERS)
    return payload
