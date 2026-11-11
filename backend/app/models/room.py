from sqlalchemy import Boolean, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, BranchScoped


class Room(BranchScoped, BaseModel):
    """Kabinet. Nomi filial ichida registrsiz unikal."""

    __tablename__ = "rooms"
    __table_args__ = (Index("uq_rooms_branch_name_lower", "branch_id", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

