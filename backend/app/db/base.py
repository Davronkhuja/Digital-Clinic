import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, MetaData, String, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_col(enum_cls, name: str, length: int = 20) -> SAEnum:
    """Matn ustun + CHECK (native PG enum emas): migratsiyalar oson bo'ladi."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda e: [m.value for m in e],
    )


class BaseModel(Base):
    """Barcha jadvallar uchun umumiy: UUID PK (server tomonida), vaqt belgilari, created_by."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # users.id; FK yo'q: users -> staff -> branches zanjiri bilan dumaloq bog'liqlik bo'lmasligi uchun
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class BranchScoped:
    """branch_id: ko'p filialli ish uchun hozirdan (standart filial seed qilinadi)."""

    @declared_attr
    def branch_id(cls) -> Mapped[uuid.UUID]:
        from sqlalchemy import ForeignKey

        return mapped_column(UUID(as_uuid=True), ForeignKey("branches.id", ondelete="RESTRICT"), index=True)


class SoftDeleteMixin:
    """EMR, retsept va to'lov yozuvlari hech qachon o'chirilmaydi: deleted_at qo'yiladi."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerifiedMixin:
    """Ma'lumotnoma yozuvi tekshirilganmi (`verified`) va qayerdan (`source`). Starter/namuna yozuvlar `verified=false`;
    rasmiy fayl import qilinganda yoki administrator tasdiqlaganda `true`."""

    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    source: Mapped[str | None] = mapped_column(String(200))
