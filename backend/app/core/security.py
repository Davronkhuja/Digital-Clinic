import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

security = HTTPBearer(auto_error=False)


def new_id() -> str:
    return str(uuid.uuid4())


def hash_password(password: str) -> str:
    # bcrypt faqat birinchi 72 baytni hisobga oladi
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


def _users():
    from app.db import fake  # kech import: sikl bo'lmasligi uchun
    return fake.fake_users


def _create_token(user: dict, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user["email"], "uid": user["id"], "role": user["role"], "type": token_type,
               "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def create_access_token(user: dict) -> str:
    return _create_token(user, "access", timedelta(minutes=settings.access_token_expire_minutes))

def create_refresh_token(user: dict) -> str:
    return _create_token(user, "refresh", timedelta(days=settings.refresh_token_expire_days))

def decode_token(token: str, expected_type: str) -> dict:
    """Tokenni tekshiradi; yaroqsiz, eskirgan yoki turi noto'g'ri bo'lsa 401."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                             options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan",
                            headers={"WWW-Authenticate": "Bearer"})
    if payload.get("type") != expected_type:
        raise HTTPException(status_code=401, detail="Token turi noto'g'ri",
                            headers={"WWW-Authenticate": "Bearer"})
    return payload

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    payload = decode_token(credentials.credentials, "access")
    user = _users().get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan",
                            headers={"WWW-Authenticate": "Bearer"})
    return {"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]}
