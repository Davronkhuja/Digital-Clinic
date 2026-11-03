import csv  # noqa: F401
import io  # noqa: F401
from datetime import date, datetime  # noqa: F401
from typing import List, Optional  # noqa: F401

from fastapi import APIRouter, Depends, HTTPException, Query, status  # noqa: F401
from fastapi.responses import Response  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.core.security import *  # noqa: F401,F403
from app.db import fake  # noqa: F401
from app.schemas import *  # noqa: F401,F403

router = APIRouter()

# ── AUTH ──────────────────────────────────────
@router.post("/auth/login", tags=["🔐 Auth"], response_model=TokenResponse,
          summary="Tizimga kirish", description="Email va parol orqali tizimga kiring va JWT token oling.")
def login(data: LoginRequest):
    user = fake.fake_users.get(data.email)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email yoki parol noto'g'ri")
    return TokenResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user), user={"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@router.post("/auth/refresh", tags=["🔐 Auth"], response_model=TokenResponse,
          summary="Access tokenni yangilash",
          description="Refresh token (7 kun) bilan yangi access (30 daqiqa) va yangi refresh token oling.")
def refresh(data: RefreshRequest):
    payload = decode_token(data.refresh_token, "refresh")
    user = fake.fake_users.get(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati tugagan")
    return TokenResponse(access_token=create_access_token(user), refresh_token=create_refresh_token(user),
                         user={"id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]})

@router.post("/auth/register", tags=["🔐 Auth"], status_code=status.HTTP_201_CREATED,
          summary="Yangi hisob yaratish", description="Yangi klinika uchun admin hisob yarating.")
def register(data: RegisterRequest):
    if data.email in fake.fake_users:
        raise HTTPException(status_code=400, detail="Bu email allaqachon ro'yxatdan o'tgan")
    fake.fake_users[data.email] = {
        "id": new_id(), "name": data.name, "email": data.email,
        "password_hash": hash_password(data.password), "role": "admin"
    }
    return {"message": "Muvaffaqiyatli ro'yxatdan o'tdingiz", "email": data.email}

@router.post("/auth/forgot-password", tags=["🔐 Auth"],
          summary="Parolni tiklash (hozircha mavjud emas)", description="Email orqali tiklash hali amalga oshirilmagan; 501 qaytaradi.")
def forgot_password(data: ForgotPasswordRequest):
    # Email yuborish hozircha yo'q: yolg'on "yuborildi" javobi o'rniga halol 501
    raise HTTPException(status_code=501, detail="Parolni tiklash uchun administratorga murojaat qiling")
