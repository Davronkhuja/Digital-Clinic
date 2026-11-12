"""Filial sozlamalari (clinic_settings) dan moliya/xabarlar sozlamalarini o'qish; qator yo'q bo'lsa standartlar."""
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClinicSettings

DEFAULT_DISCOUNT_LIMIT = Decimal("10")


def clinic_row(db: Session, branch_id: uuid.UUID) -> ClinicSettings | None:
    return db.scalar(select(ClinicSettings).where(ClinicSettings.branch_id == branch_id))


def discount_limit(db: Session, branch_id: uuid.UUID) -> Decimal:
    row = clinic_row(db, branch_id)
    return row.discount_limit_percent if row else DEFAULT_DISCOUNT_LIMIT
