# ruff: noqa: E501
"""Sug'urta mantiqi: polis/shartnoma amal qilishi, kafolat xati holati va ishlatilgan summa."""
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuaranteeLetter, InsuranceContract, PatientPolicy
from app.services.money import q2
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


@dataclass
class Context:
    policy: PatientPolicy
    contract: InsuranceContract
    letter: GuaranteeLetter | None = None


def load_context(db: Session, patient_id: uuid.UUID, policy_id: uuid.UUID | None, letter_id: uuid.UUID | None,
                 exclude_invoice_id: uuid.UUID | None = None) -> Context | None:
    """Hisob-faktura uchun sug'urta konteksti: polis bemorniki va amal qilayotgan bo'lishi, kafolat xati shu polisniki va faol bo'lishi,
    shartnoma talab qilsa kafolat xati majburiy. Aks holda 422."""
    if not policy_id:
        if letter_id:
            raise HTTPException(422, "Kafolat xati polissiz berilmaydi")
        return None
    policy = db.get(PatientPolicy, policy_id)
    if not policy or policy.patient_id != patient_id:
        raise HTTPException(422, "Polis topilmadi yoki boshqa bemorga tegishli")
    contract = db.get(InsuranceContract, policy.contract_id)
    if not policy_valid(policy, contract):
        raise HTTPException(422, "Polis yoki shartnoma amal qilmayapti (muddat yoki faollik)")
    letter = None
    if letter_id:
        letter = db.get(GuaranteeLetter, letter_id)
        if not letter or letter.policy_id != policy.id:
            raise HTTPException(422, "Kafolat xati topilmadi yoki boshqa polisga tegishli")
        used = letter_used(db, letter.id)
        if exclude_invoice_id:                       # qoralamaning o'z ulushi limitni tugatgan deb hisoblanmasin
            from sqlalchemy import func

            from app.models import Invoice
            used -= Decimal(db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
                Invoice.id == exclude_invoice_id, Invoice.guarantee_letter_id == letter.id)))
        state = letter_state(letter, used)
        if state != "Active":
            raise HTTPException(422, f"Kafolat xati faol emas ({state})")
    if contract.requires_guarantee and not letter:
        raise HTTPException(422, "Bu shartnoma bo'yicha kafolat xati talab qilinadi")
    return Context(policy, contract, letter)


def _scale(shares: list[Decimal], cap: Decimal) -> list[Decimal]:
    """Sug'urta ulushlarini umumiy `cap` ga proporsional kamaytiradi (yaxlitlash qoldig'i ulushi bor qatorlarga)."""
    total = sum(shares, ZERO)
    if total <= cap:
        return shares
    out = [q2(s * cap / total) for s in shares]
    left = cap - sum(out, ZERO)
    for i, s in enumerate(shares):
        if left <= 0:
            break
        extra = min(left, s - out[i])
        out[i] += extra
        left -= extra
    return out


def split(db: Session, ctx: Context, computed, exclude_invoice_id: uuid.UUID | None = None) -> Decimal:
    """Har qatorning sug'urta ulushini hisoblaydi (`insurer_amount`) va umumiy sug'urta ulushini qaytaradi.
    Qoplash: shartnomadagi xizmat foizi (yoki `coverage_all`: standart foiz), kafolat xati xizmatlar ro'yxati bilan cheklasa shu xizmatlar.
    Limitlar: bitta hisob-faktura, bemor uchun kalendar yil (shu shartnoma bo'yicha oldingi hisob-fakturalar), kafolat xati qoldig'i."""
    from sqlalchemy import extract, func

    from app.models import GuaranteeLetterService, InsuranceContractService, Invoice
    from app.schemas.enums import InvoiceStatus
    c = ctx.contract
    coverage = {r.service_id: r.coverage_percent for r in db.scalars(select(InsuranceContractService).where(InsuranceContractService.contract_id == c.id))}
    allowed = None
    if ctx.letter:
        allowed = set(db.scalars(select(GuaranteeLetterService.service_id).where(GuaranteeLetterService.letter_id == ctx.letter.id))) or None
    shares = []
    for ln in computed.lines:
        pct = coverage.get(ln.service.id, c.default_coverage_percent if c.coverage_all else None)
        covered = pct is not None and (allowed is None or ln.service.id in allowed)
        shares.append(q2(ln.net_total * pct / 100) if covered else ZERO)
    caps = []
    if c.per_visit_limit is not None:
        caps.append(c.per_visit_limit)
    if c.annual_limit is not None:
        year = clinic_today().year
        policies = select(PatientPolicy.id).where(PatientPolicy.patient_id == ctx.policy.patient_id, PatientPolicy.contract_id == c.id)
        stmt = select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
            Invoice.policy_id.in_(policies), Invoice.status != InvoiceStatus.cancelled, extract("year", Invoice.created_at) == year)
        if exclude_invoice_id:
            stmt = stmt.where(Invoice.id != exclude_invoice_id)
        caps.append(max(c.annual_limit - Decimal(db.scalar(stmt)), ZERO))
    if ctx.letter:
        used = letter_used(db, ctx.letter.id)
        if exclude_invoice_id:
            used -= Decimal(db.scalar(select(func.coalesce(func.sum(Invoice.insurer_total), 0)).where(
                Invoice.id == exclude_invoice_id, Invoice.guarantee_letter_id == ctx.letter.id, Invoice.status != InvoiceStatus.cancelled)))
        caps.append(max(ctx.letter.amount_limit - used, ZERO))
    if caps:
        shares = _scale(shares, min(caps))
    for ln, share in zip(computed.lines, shares, strict=True):
        ln.insurer_amount = share
    return sum(shares, ZERO)


def resplit_invoice(db: Session, inv) -> None:
    """Qoralama chiqarilganda: polis, kafolat xati va limitlar qayta tekshiriladi, sug'urta ulushi qayta hisoblanadi."""
    from types import SimpleNamespace

    from app.models import InvoiceLine
    ctx = load_context(db, inv.patient_id, inv.policy_id, inv.guarantee_letter_id, exclude_invoice_id=inv.id)
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    proxy = SimpleNamespace(lines=[SimpleNamespace(service=SimpleNamespace(id=ln.service_id), net_total=ln.net_total, insurer_amount=ZERO) for ln in lines])
    inv.insurer_total = split(db, ctx, proxy, exclude_invoice_id=inv.id)
    for ln, p in zip(lines, proxy.lines, strict=True):
        ln.insurer_amount = p.insurer_amount
