from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import CurrentUser, get_current_user, load_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services import audit
from app.services import auth as auth_service

router = APIRouter()

# Mavjud bo'lmagan foydalanuvchi uchun ham bcrypt vaqti sarflansin (email enumeratsiyasiga qarshi)
_DUMMY_HASH = hash_password("dummy-password")


@router.post("/auth/login", tags=["🔐 Auth"], response_model=TokenResponse, summary="Tizimga kirish",
             description="Email va parol orqali tizimga kiring va JWT token oling.")
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not ok:
        audit.record(db, None, request, "login_failed", "auth", user_id=user.id if user else None,
                     details={"email": data.email.lower()})
        db.commit()
        raise HTTPException(401, "Email yoki parol noto'g'ri")
    if not user.is_active:
        audit.record(db, None, request, "login_failed", "auth", user_id=user.id,
                     details={"email": data.email.lower(), "reason": "inactive"})
        db.commit()
        raise HTTPException(403, "Hisob faol emas. Administratorga murojaat qiling")
    user.last_login_at = datetime.now(UTC)
    current = load_current_user(db, user.id)
    audit.record(db, current, request, "login", "auth")
    return auth_service.issue_tokens(db, current, request)


@router.post("/auth/refresh", tags=["🔐 Auth"], response_model=TokenResponse, summary="Access tokenni yangilash",
             description="Refresh token (7 kun) bilan yangi access (30 daqiqa) va yangi refresh token oling.")
def refresh(data: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    return auth_service.rotate_refresh(db, data.refresh_token, request)


@router.post("/auth/logout", tags=["🔐 Auth"], summary="Chiqish (refresh tokenni bekor qilish)")
def logout(data: LogoutRequest, request: Request, user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    auth_service.revoke_refresh(db, data.refresh_token, user.id)
    audit.record(db, user, request, "logout", "auth")
    db.commit()
    return {"message": "Chiqdingiz"}


@router.get("/auth/me", tags=["🔐 Auth"], summary="Joriy foydalanuvchi")
def me(user: CurrentUser = Depends(get_current_user)):
    return user.public()


@router.post("/auth/change-password", tags=["🔐 Auth"], summary="Parolni o'zgartirish",
             description="Parol o'zgarganda barcha refresh tokenlar bekor qilinadi.")
def change_password(data: ChangePasswordRequest, request: Request, user: CurrentUser = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    row = db.get(User, user.id)
    if not verify_password(data.current_password, row.password_hash):
        raise HTTPException(400, "Joriy parol noto'g'ri")
    row.password_hash = hash_password(data.new_password)
    auth_service.revoke_all(db, user.id)
    audit.record(db, user, request, "change_password", "user", user.id)
    db.commit()
    return {"message": "Parol o'zgartirildi. Barcha qurilmalardan qayta kiring"}


@router.post("/auth/forgot-password", tags=["🔐 Auth"],
             summary="Parolni tiklash (hozircha mavjud emas)",
             description="Email orqali tiklash hali amalga oshirilmagan; 501 qaytaradi.")
def forgot_password(data: ForgotPasswordRequest):
    raise HTTPException(501, "Parolni tiklash uchun administratorga murojaat qiling")
