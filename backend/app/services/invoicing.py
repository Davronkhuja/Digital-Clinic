"""Hisob-faktura hisobi: qator chegirmasi, hisob-faktura chegirmasini qatorlarga proporsional taqsimlash, QQS (narx QQS bilan:
QQS = net * p / (100 + p)). Pul faqat Decimal, 2 xonaga `money.q2`."""
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException

from app.models import Service
from app.services.money import q2

ZERO = Decimal("0.00")


@dataclass
class LineInput:
    service: Service
    quantity: int = 1
    doctor_id: object | None = None
    discount_percent: Decimal | None = None
    discount_amount: Decimal | None = None


@dataclass
class ComputedLine:
    service: Service
    quantity: int
    doctor_id: object | None
    unit_price: Decimal
    line_discount: Decimal
    invoice_discount_share: Decimal
    net_total: Decimal
    vat_amount: Decimal


@dataclass
class Computed:
    lines: list[ComputedLine]
    subtotal: Decimal
    discount_total: Decimal
    total: Decimal
    vat_total: Decimal


def compute(lines: list[LineInput], discount_percent: Decimal | None, discount_amount: Decimal | None) -> Computed:
    gross, after_line, line_disc = [], [], []
    for i, ln in enumerate(lines, 1):
        g = q2(ln.service.price * ln.quantity)
        if ln.discount_percent is not None:
            d = q2(g * ln.discount_percent / 100)
        elif ln.discount_amount is not None:
            d = q2(ln.discount_amount)
            if d > g:
                raise HTTPException(422, f"{i}-qator chegirmasi qator summasidan katta")
        else:
            d = ZERO
        gross.append(g)
        line_disc.append(d)
        after_line.append(g - d)
    base = sum(after_line, ZERO)

    if discount_percent is not None:
        invoice_disc = q2(base * discount_percent / 100)
    elif discount_amount is not None:
        invoice_disc = q2(discount_amount)
        if invoice_disc > base:
            raise HTTPException(422, "Chegirma hisob-faktura summasidan katta")
    else:
        invoice_disc = ZERO

    shares = [ZERO] * len(lines)
    if invoice_disc and base:
        allocated = ZERO
        for i, a in enumerate(after_line):
            share = invoice_disc - allocated if i == len(lines) - 1 else q2(invoice_disc * a / base)
            share = min(share, a, invoice_disc - allocated)
            shares[i] = share
            allocated += share
        leftover = invoice_disc - allocated  # yaxlitlash qoldig'i: sig'adigan qatorlarga
        for i, a in enumerate(after_line):
            if leftover <= 0:
                break
            extra = min(leftover, a - shares[i])
            shares[i] += extra
            leftover -= extra

    out: list[ComputedLine] = []
    for ln, d, share, a in zip(lines, line_disc, shares, after_line, strict=True):
        net = a - share
        p = ln.service.vat_percent
        out.append(ComputedLine(ln.service, ln.quantity, ln.doctor_id, ln.service.price, d, share, net,
                                q2(net * p / (100 + p))))
    return Computed(out, sum(gross, ZERO), sum((c.line_discount + c.invoice_discount_share for c in out), ZERO),
                    sum((c.net_total for c in out), ZERO), sum((c.vat_amount for c in out), ZERO))


def require_sellable(services: dict) -> None:
    """Bularsiz (MXIK/package_code/QQS yo'q yoki nofaol) xizmatni sotib bo'lmaydi."""
    problems = []
    for service in services.values():
        if not service.is_active:
            problems.append(f"{service.name}: faol emas")
        elif service.missing_fields:
            problems.append(f"{service.name}: yetishmaydi {', '.join(service.missing_fields)}")
    if problems:
        raise HTTPException(422, "Xizmatni sotib bo'lmaydi (MXIK, package_code va QQS to'liq bo'lishi kerak): " + "; ".join(problems))
