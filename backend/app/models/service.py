import uuid
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class ServiceCategory(BaseModel):
    __tablename__ = "service_categories"
    __table_args__ = (Index("uq_service_categories_name_lower", func.lower(text("name")), unique=True),)

    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Service(BaseModel):
    """Narxnoma xizmati. Soliq/fiskal chek uchun MXIK (IKPU, 17 raqam), `package_code` va QQS foizi kerak: ulardan birortasi
    bo'lmasa xizmat saqlanadi, lekin sotib bo'lmaydi (`sellable=false`). Narx QQS bilan (soliq hisobida QQS undan ajratiladi).
    Hisob-fakturada narx va soliq maydonlari nusxalanadi; xizmat o'chirilmaydi, faolsizlantiriladi."""

    __tablename__ = "services"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("mxik IS NULL OR mxik ~ '^[0-9]{17}$'", name="mxik_format"),
        CheckConstraint("package_code IS NULL OR package_code ~ '^[0-9]{1,10}$'", name="package_code_format"),
        CheckConstraint("vat_percent IS NULL OR (vat_percent >= 0 AND vat_percent <= 100)", name="vat_range"),
        Index("uq_services_name_lower", func.lower(text("name")), unique=True),
    )

    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("service_categories.id", ondelete="SET NULL"))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    mxik: Mapped[str | None] = mapped_column(String(17))
    package_code: Mapped[str | None] = mapped_column(String(10))
    vat_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    @property
    def missing_fields(self) -> list[str]:
        return [name for name, value in (("mxik", self.mxik), ("package_code", self.package_code), ("vat_percent", self.vat_percent))
                if value is None]

    @property
    def sellable(self) -> bool:
        return self.is_active and not self.missing_fields
