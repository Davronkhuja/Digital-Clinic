import uuid
from dataclasses import dataclass, field, replace

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import UNAUTHORIZED_HEADERS, decode_token
from app.db.session import get_db
from app.models import Branch, Role, Staff, User

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: uuid.UUID
    staff_id: uuid.UUID
    name: str
    email: str
    role: str  # roles.code
    branch_id: uuid.UUID
    permissions: frozenset[str] = field(default_factory=frozenset)

    def public(self) -> dict:
        return {"id": str(self.id), "name": self.name, "email": self.email, "role": self.role, "branch_id": str(self.branch_id),
                "permissions": sorted(self.permissions)}


def load_current_user(db: Session, user_id: uuid.UUID) -> CurrentUser | None:
    row = db.execute(
        select(User, Staff, Role).join(Staff, User.staff_id == Staff.id).join(Role, User.role_id == Role.id)
        .where(User.id == user_id, User.is_active.is_(True))
    ).first()
    if not row:
        return None
    user, staff, role = row
    return CurrentUser(
        id=user.id, staff_id=staff.id, name=staff.full_name, email=user.email, role=role.code,
        branch_id=user.branch_id, permissions=frozenset(p.code for p in role.permissions),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db),
    x_branch_id: str | None = Header(None, description="Faol filial (`branches:all` kerak); bo'sh: o'z filiali"),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(401, "Authentication required", headers=UNAUTHORIZED_HEADERS)
    payload = decode_token(credentials.credentials, "access")
    user = load_current_user(db, uuid.UUID(payload["sub"]))
    if not user:
        raise HTTPException(401, "Token yaroqsiz yoki muddati tugagan", headers=UNAUTHORIZED_HEADERS)
    if x_branch_id and x_branch_id != str(user.branch_id):
        # Filial almashtirish: so'rov shu filial nomidan bajariladi (yozuvlar, ro'yxatlar, audit)
        if "branches:all" not in user.permissions:
            raise HTTPException(403, "Boshqa filialga o'tish ruxsati yo'q: branches:all")
        try:
            target = db.get(Branch, uuid.UUID(x_branch_id))
        except ValueError:
            raise HTTPException(422, "X-Branch-Id noto'g'ri")
        if not target or not target.is_active:
            raise HTTPException(400, "Filial topilmadi yoki faol emas")
        user = replace(user, branch_id=target.id)
    return user


def require(*needed: str):
    """Ruxsat dependency: foydalanuvchida barcha ko'rsatilgan ruxsatlar bo'lishi shart, aks holda 403."""

    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        missing = [p for p in needed if p not in user.permissions]
        if missing:
            raise HTTPException(403, f"Ruxsat yo'q: {', '.join(missing)}")
        return user

    return checker
