from typing import Optional

from pydantic import BaseModel


class AuditEntry(BaseModel):
    id: str
    created_at: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    ip: Optional[str] = None
    details: Optional[dict] = None


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


class SessionOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    email: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    last_active: str
    expires_at: str
