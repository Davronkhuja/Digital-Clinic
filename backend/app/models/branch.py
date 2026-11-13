from sqlalchemy import Boolean, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Branch(BaseModel):
    __tablename__ = "branches"
    __table_args__ = (Index("uq_branches_name_lower", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
