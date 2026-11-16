# ruff: noqa: E501
"""Shifokor foizi: qoida tanlash, to'lovda hisoblash (accrual), qaytarishda proporsional teskari yozuv (reversal), oylik hisobot.
Hamma summa Decimal/numeric(14,2). Asos: to'lov ulushi (qatorlarga `allocate` bilan), QQS bilan yoki QQS ajratilgan (qoida bo'yicha)."""
import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CommissionEntry, CommissionRule, InsurerPayment, Invoice, InvoiceLine, Payment, PaymentRefund
from app.schemas.enums import CommissionBase, CommissionEntryKind, CommissionKind
from app.services import app_settings
from app.services.invoicing import allocate
from app.services.money import q2
from app.services.periods import CLINIC_TZ, clinic_today

ZERO = Decimal("0.00")


def resolve_rule(db: Session, doctor_id: uuid.UUID, service_id: uuid.UUID, on: date) -> CommissionRule | None:
    """Eng aniq qoida: shifokor+xizmat > shifokor > xizmat > umumiy; teng bo'lsa valid_from kechroq."""
    rules = db.scalars(select(CommissionRule).where(
        CommissionRule.is_active.is_(True), CommissionRule.valid_from <= on,
        (CommissionRule.valid_to.is_(None)) | (CommissionRule.valid_to >= on),
        (CommissionRule.doctor_id == doctor_id) | CommissionRule.doctor_id.is_(None),
        (CommissionRule.service_id == service_id) | CommissionRule.service_id.is_(None))).all()
    if not rules:
        return None
    return max(rules, key=lambda r: ((r.doctor_id is not None) * 2 + (r.service_id is not None), r.valid_from, r.created_at))


def _commission(rule: CommissionRule, line: InvoiceLine, share: Decimal, kind: CommissionBase) -> tuple[Decimal, Decimal]:
    """(asos, foiz summasi) to'lov ulushi `share` uchun; `kind`: qoida asosi yoki sozlamadagi standart."""
    vat = q2(share * line.vat_percent / (100 + line.vat_percent))
    base = share - vat if kind == CommissionBase.net_of_vat else share
    if rule.kind == CommissionKind.percent:
        return base, q2(base * rule.percent / 100)
    full = q2(rule.fixed_amount * line.quantity)  # qat'iy summa har sotilgan birlik uchun; qisman to'lovda ulushga proporsional
    return base, q2(full * share / line.net_total) if line.net_total else ZERO


def accrue(db: Session, payment: Payment, inv: Invoice) -> list[CommissionEntry]:
    lines = list(db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position)))
    today = (payment.paid_at.astimezone(CLINIC_TZ).date() if payment.paid_at else clinic_today())
    default_kind = CommissionBase(app_settings.commission_base(db, payment.branch_id))  # sozlama hisoblash paytida: keyingilarga ta'sir qiladi
    out = []
    for line, share in allocate(lines, payment.amount):
        if share <= 0 or not line.doctor_id:
            continue
        rule = resolve_rule(db, line.doctor_id, line.service_id, today)
        if not rule:
            continue
        kind = rule.base or default_kind
        base, amount = _commission(rule, line, share, kind)
        entry = CommissionEntry(kind=CommissionEntryKind.accrual, doctor_id=line.doctor_id, service_id=line.service_id, payment_id=payment.id,
                                invoice_line_id=line.id, rule_id=rule.id, rule_kind=rule.kind, rule_percent=rule.percent,
                                rule_fixed=rule.fixed_amount, base_kind=kind, base_amount=base, amount=amount, entry_date=today,
                                branch_id=payment.branch_id, created_by=payment.created_by)
        db.add(entry)
        out.append(entry)
    db.flush()
    return out


def reconcile_insurer(db: Session, insurer_id: uuid.UUID, trigger: InsurerPayment, actor_id: uuid.UUID | None) -> list[CommissionEntry]:
    """Sug'urta ulushidan foiz: kompaniya to'lagan (FIFO taqsimlangan) summa uchun. Har qator uchun "maqsad" (to'langan ulushdan foiz) bilan
    avval yozilgan Insurer yozuvlari yig'indisi farqi yoziladi: to'lov kelsa accrual (+), bekor qilinsa reversal (-). Idempotent.
    `PatientOnly` sozlamada hisoblanmaydi. Qoida birinchi yozuvdan nusxalanadi (keyin o'zgarsa eski hisob buzilmaydi)."""
    from app.services.insurance import fifo_allocations
    today = clinic_today()
    out = []
    for inv, allocated in fifo_allocations(db, insurer_id):
        if app_settings.commission_scope(db, inv.branch_id) != "FullAmount":
            continue
        lines = [ln for ln in db.scalars(select(InvoiceLine).where(InvoiceLine.invoice_id == inv.id).order_by(InvoiceLine.position))
                 if (ln.insurer_amount or ZERO) > 0]
        left = allocated
        for i, ln in enumerate(lines):
            share = left if i == len(lines) - 1 else q2(allocated * ln.insurer_amount / inv.insurer_total)
            share = min(share, left)
            left -= share
            if not ln.doctor_id:
                continue
            prev = db.scalars(select(CommissionEntry).where(CommissionEntry.invoice_line_id == ln.id, CommissionEntry.source == "Insurer")
                              .order_by(CommissionEntry.created_at)).all()
            first = prev[0] if prev else None
            if first:
                rule = SimpleNamespace(kind=first.rule_kind, percent=first.rule_percent, fixed_amount=first.rule_fixed, id=first.rule_id)
                kind = first.base_kind
            else:
                rule = resolve_rule(db, ln.doctor_id, ln.service_id, today)
                if not rule or share <= 0:
                    continue
                kind = rule.base or CommissionBase(app_settings.commission_base(db, inv.branch_id))
            vat = q2(share * ln.vat_percent / (100 + ln.vat_percent))
            target_base = share - vat if kind == CommissionBase.net_of_vat else share
            if rule.kind == CommissionKind.percent:
                target = q2(target_base * rule.percent / 100)
            else:
                target = q2(q2(rule.fixed_amount * ln.quantity) * share / ln.net_total) if ln.net_total else ZERO
            d_amount = target - q2(sum((e.amount for e in prev), ZERO))
            d_base = target_base - q2(sum((e.base_amount for e in prev), ZERO))
            if d_amount == 0 and d_base == 0:
                continue
            accrual = d_amount > 0 or (d_amount == 0 and d_base > 0)
            entry = CommissionEntry(kind=CommissionEntryKind.accrual if accrual else CommissionEntryKind.reversal, source="Insurer", doctor_id=ln.doctor_id,
                                    service_id=ln.service_id, payment_id=None, insurer_payment_id=trigger.id, invoice_line_id=ln.id,
                                    rule_id=rule.id, rule_kind=rule.kind, rule_percent=rule.percent, rule_fixed=rule.fixed_amount, base_kind=kind,
                                    base_amount=d_base, amount=d_amount, entry_date=today, branch_id=inv.branch_id, created_by=actor_id)
            db.add(entry)
            out.append(entry)
    db.flush()
    return out


def reverse(db: Session, refund: PaymentRefund, payment: Payment) -> list[CommissionEntry]:
    """Qaytarishda foiz ham qaytariladi: har accrual uchun jami qaytarilgan ulushga proporsional maqsad - avval qaytarilgan."""
    accruals = db.scalars(select(CommissionEntry).where(CommissionEntry.payment_id == payment.id,
                                                       CommissionEntry.kind == CommissionEntryKind.accrual)).all()
    refunded = q2(db.scalar(select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(PaymentRefund.payment_id == payment.id)))
    ratio = refunded / payment.amount
    out = []
    for e in accruals:
        done_amount = db.scalar(select(func.coalesce(func.sum(CommissionEntry.amount), 0)).where(CommissionEntry.accrual_id == e.id))
        done_base = db.scalar(select(func.coalesce(func.sum(CommissionEntry.base_amount), 0)).where(CommissionEntry.accrual_id == e.id))
        d_amount = q2(e.amount * ratio) + q2(done_amount)  # done_* manfiy
        d_base = q2(e.base_amount * ratio) + q2(done_base)
        if d_amount <= 0 and d_base <= 0:
            continue
        entry = CommissionEntry(kind=CommissionEntryKind.reversal, doctor_id=e.doctor_id, service_id=e.service_id, payment_id=payment.id,
                                refund_id=refund.id, invoice_line_id=e.invoice_line_id, accrual_id=e.id, rule_id=e.rule_id,
                                rule_kind=e.rule_kind, rule_percent=e.rule_percent, rule_fixed=e.rule_fixed, base_kind=e.base_kind,
                                base_amount=-max(d_base, ZERO), amount=-max(d_amount, ZERO), entry_date=clinic_today(),
                                branch_id=payment.branch_id, created_by=refund.created_by)
        db.add(entry)
        out.append(entry)
    db.flush()
    return out


def month_bounds(month: str) -> tuple[date, date]:
    """'2026-11' -> (2026-11-01, 2026-12-01)."""
    year, mon = (int(x) for x in month.split("-"))
    start = date(year, mon, 1)
    return start, date(year + (mon == 12), mon % 12 + 1, 1)
