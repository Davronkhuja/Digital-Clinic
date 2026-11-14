# ruff: noqa: E501
"""Sug'urta mantiqi: polis/shartnoma amal qilishi, kafolat xati holati va ishlatilgan summa."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuaranteeLetter, InsuranceContract, PatientPolicy
from app.services.periods import clinic_today

ZERO = Decimal("0.00")


def policy_valid(policy: PatientPolicy, contract: InsuranceContract, on: date | None = None) -> bool:
    on = on or clinic_today()
    return (policy.is_active and policy.valid_from <= on and (policy.valid_to is None or policy.valid_to >= on)
            and contract.is_active and contract.valid_from <= on and (contract.valid_to is None or contract.valid_to >= on))


def letter_used(db: Session, letter_id: uuid.UUID) -> Decimal:
    """Kafolat xati bo'yicha ishlatilgan sug'urta ulushi (shu xatga bog'langan, bekor qilinmagan hisob-fakturalar)."""
    from sqlalchemy import func

    from app.models import Invoice
    from app.schemas.enums import InvoiceStatus
    if not hasattr(Invoice, "guarantee_letter_id"):          # hisob-faktura bo'linishi (keyingi versiya) qo'shilguncha ishlatilgan summa 0
        return ZERO
    total = db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
        Invoice.guarantee_letter_id == letter_id, Invoice.status != InvoiceStatus.cancelled))
    return Decimal(total)


def letter_state(letter: GuaranteeLetter, used: Decimal, on: date | None = None) -> str:
    on = on or clinic_today()
    if letter.status == "Cancelled":
        return "Cancelled"
    if (letter.valid_to and letter.valid_to < on) or (letter.valid_from and letter.valid_from > on):
        return "Expired"
    return "Exhausted" if used >= letter.amount_limit else "Active"
