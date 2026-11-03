"""Audit jurnali: kim, qachon, nimani qildi (bemor, EMR, to'lov yozuvlari va autentifikatsiya hodisalari)."""
import ipaddress
import uuid
from functools import lru_cache

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser
from app.models import AuditLog


@lru_cache
def _trusted_networks() -> tuple:
    return tuple(ipaddress.ip_network(n.strip()) for n in settings.trusted_proxies.split(",") if n.strip())


def _is_trusted(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in _trusted_networks())


def client_ip(request: Request) -> str | None:
    """Real mijoz IP'si. X-Forwarded-For faqat ishonchli proksidan kelgan bo'lsa hisobga olinadi;
    o'ngdan chapga yurib, birinchi ishonchsiz manzil olinadi (chap tomonni mijoz soxtalashtirishi mumkin)."""
    peer = request.client.host if request.client else None
    if not peer or not _is_trusted(peer):
        return peer
    forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    for hop in reversed(forwarded):
        if not _is_trusted(hop):
            return hop[:45]
    return peer


def client_meta(request: Request) -> tuple[str | None, str | None]:
    ua = (request.headers.get("user-agent") or "")[:300] or None
    return client_ip(request), ua


def record(
    db: Session,
    user: CurrentUser | None,
    request: Request,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | str | None = None,
    details: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    """Yozuvni sessiyaga qo'shadi (commit chaqiruvchida: asosiy amal bilan bitta tranzaksiya)."""
    ip, ua = client_meta(request)
    db.add(
        AuditLog(
            user_id=user.id if user else user_id,
            branch_id=user.branch_id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=uuid.UUID(str(entity_id)) if entity_id else None,
            ip=ip,
            user_agent=ua,
            details=details,
            created_by=user.id if user else user_id,
        )
    )


def record_read(db: Session, user: CurrentUser, request: Request, entity_type: str, entity_id=None, details=None) -> None:
    record(db, user, request, "read", entity_type, entity_id, details)
    db.commit()
