# ruff: noqa: E501
import uuid

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped


class Notification(BranchScoped, BaseModel):
    """Xodimlar uchun ichki bildirishnoma. Filial va ruxsat bo'yicha ko'rinadi (masalan, `warehouse:write` bor xodimlar ombor ogohlantirishini ko'radi).
    `dedupe_key` bir xil ogohlantirish takrorlanmasligi uchun (noyob)."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_branch_created", "branch_id", "created_at"),)

    permission: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(30))        # stock_shortage, stock_low, stock_expiring, stock_expired
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(200))
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True)


class NotificationRead(BaseModel):
    """Bildirishnoma foydalanuvchi bo'yicha o'qilgan deb belgilanadi."""

    __tablename__ = "notification_reads"
    __table_args__ = (UniqueConstraint("notification_id", "user_id"),)

    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
