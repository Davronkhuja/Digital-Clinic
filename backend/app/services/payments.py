"""To'lovlar (v1.7.2 da to'ldiriladi). Hisob-faktura bilan bog'lanish nuqtalari."""
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session


def invoice_paid_refunded(db: Session, invoice_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    return Decimal("0.00"), Decimal("0.00")


def has_payments(db: Session, invoice_id: uuid.UUID) -> bool:
    return False
