# ruff: noqa: E501
"""Sug'urta reyestri hujjati: qatorlarni hisoblash (asl + tuzatish), yuborish (qotirish), Excel."""
import hashlib
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    GuaranteeLetter,
    InsuranceContract,
    InsuranceRegistry,
    InsuranceRegistryLine,
    Insurer,
    InsurerPayment,
    Invoice,
    InvoiceLine,
    Patient,
    PatientPolicy,
)
from app.schemas.enums import InvoiceStatus
from app.services import insurance as ins
from app.services.periods import CLINIC_TZ

ZERO = Decimal("0.00")
VALID = [InvoiceStatus.issued, InvoiceStatus.partially_paid, InvoiceStatus.paid]
SENT = ("Sent", "Reconciled")


def month_first(month: str) -> date:
    return date(int(month[:4]), int(month[5:]), 1)


def month_last(first: date) -> date:
    return date(first.year + (first.month == 12), first.month % 12 + 1, 1) - timedelta(days=1)


def make_number(insurer_id: uuid.UUID, first: date, branch_id: uuid.UUID) -> str:
    return f"REE-{first:%Y%m}-{str(insurer_id)[:4].upper()}-{str(branch_id)[:2].upper()}"


def _base_select():
    day = cast(func.timezone(str(CLINIC_TZ), Invoice.issued_at), Date)
    return day, (select(InvoiceLine, Invoice, day, Patient.full_name, PatientPolicy.number, GuaranteeLetter.number, InsuranceContract.number, Branch.name)
                 .join(Invoice, InvoiceLine.invoice_id == Invoice.id).join(Patient, Invoice.patient_id == Patient.id)
                 .outerjoin(PatientPolicy, Invoice.policy_id == PatientPolicy.id).outerjoin(InsuranceContract, PatientPolicy.contract_id == InsuranceContract.id)
                 .outerjoin(GuaranteeLetter, Invoice.guarantee_letter_id == GuaranteeLetter.id).join(Branch, Invoice.branch_id == Branch.id))


def _row(ln, inv, d, patient, policy, letter, contract, branch, kind, qty, total, share) -> dict:
    return {"invoice_line_id": ln.id, "kind": kind, "date": d, "invoice": inv.number, "patient": patient, "policy": policy, "letter": letter, "contract": contract,
            "service": ln.name if kind == "Original" else f"Tuzatish: {ln.name}", "qty": qty, "line_total": total, "insurer_amount": share, "patient_amount": total - share,
            "branch": branch}


def registered(db: Session, insurer_id: uuid.UUID, branch_id: uuid.UUID) -> dict[uuid.UUID, tuple[int, Decimal, Decimal]]:
    """Avval yuborilgan reyestrlardagi qatorlar bo'yicha jami: {invoice_line_id: (soni, summa, sug'urta ulushi)}."""
    stmt = (select(InsuranceRegistryLine.invoice_line_id, func.sum(InsuranceRegistryLine.qty), func.sum(InsuranceRegistryLine.line_total),
                   func.sum(InsuranceRegistryLine.insurer_amount))
            .join(InsuranceRegistry, InsuranceRegistryLine.registry_id == InsuranceRegistry.id)
            .where(InsuranceRegistry.insurer_id == insurer_id, InsuranceRegistry.branch_id == branch_id, InsuranceRegistry.status.in_(SENT))
            .group_by(InsuranceRegistryLine.invoice_line_id))
    return {lid: (int(q), Decimal(t), Decimal(s)) for lid, q, t, s in db.execute(stmt).all()}


def live_rows(db: Session, insurer_id: uuid.UUID, first: date, branch_id: uuid.UUID) -> list[dict]:
    """Hozirgi holatga ko'ra reyestr qatorlari: (1) oy oxirigacha chiqarilgan va hali ro'yxatga olinmagan qatorlar (Original),
    (2) avval yuborilgan qatorlardan farq qilganlari (Correction: musbat yoki manfiy farq; bekor qilingan hisob-faktura to'liq manfiy)."""
    done = registered(db, insurer_id, branch_id)
    day, base = _base_select()
    last = month_last(first)
    originals = base.where(Invoice.insurer_id == insurer_id, Invoice.branch_id == branch_id, InvoiceLine.insurer_amount > 0, Invoice.status.in_(VALID),
                           day <= last).order_by(Invoice.issued_at, Invoice.number, InvoiceLine.position)
    rows = []
    for ln, inv, d, patient, policy, letter, contract, branch in db.execute(originals).all():
        if ln.id in done:
            continue
        rows.append(_row(ln, inv, d, patient, policy, letter, contract, branch, "Original", ln.quantity, ln.net_total, ln.insurer_amount))
    if done:
        cur = base.where(InvoiceLine.id.in_(list(done))).order_by(Invoice.issued_at, Invoice.number, InvoiceLine.position)
        for ln, inv, d, patient, policy, letter, contract, branch in db.execute(cur).all():
            valid = inv.status in VALID
            qty, total, share = (ln.quantity, ln.net_total, ln.insurer_amount or ZERO) if valid else (0, ZERO, ZERO)
            pq, pt, ps = done[ln.id]
            if (qty, total, share) != (pq, pt, ps):
                rows.append(_row(ln, inv, d, patient, policy, letter, contract, branch, "Correction", qty - pq, total - pt, share - ps))
    return rows


def totals(rows: list[dict]) -> dict:
    return {"insurer_total": sum((r["insurer_amount"] for r in rows), ZERO), "patient_total": sum((r["patient_amount"] for r in rows), ZERO),
            "lines_count": len(rows), "invoices_count": len({r["invoice"] for r in rows}),
            "corrections": sum(1 for r in rows if r["kind"] == "Correction")}


def frozen_rows(db: Session, reg: InsuranceRegistry) -> list[dict]:
    lines = db.scalars(select(InsuranceRegistryLine).where(InsuranceRegistryLine.registry_id == reg.id).order_by(InsuranceRegistryLine.created_at,
                                                                                                                 InsuranceRegistryLine.invoice_number)).all()
    return [{"invoice_line_id": ln.invoice_line_id, "kind": ln.kind, "date": ln.line_date, "invoice": ln.invoice_number, "patient": ln.patient, "policy": ln.policy,
             "letter": ln.letter, "contract": ln.contract, "service": ln.service, "qty": ln.qty, "line_total": ln.line_total, "insurer_amount": ln.insurer_amount,
             "patient_amount": ln.patient_amount, "branch": ln.branch} for ln in lines]


def rows_of(db: Session, reg: InsuranceRegistry) -> list[dict]:
    return live_rows(db, reg.insurer_id, reg.month, reg.branch_id) if reg.status == "Draft" else frozen_rows(db, reg)


def head_of(db: Session, reg: InsuranceRegistry, rows: list[dict]) -> dict:
    insurer = db.get(Insurer, reg.insurer_id)
    t = totals(rows) if reg.status == "Draft" else {"insurer_total": reg.insurer_total, "patient_total": reg.patient_total, "lines_count": reg.lines_count,
                                                    "invoices_count": reg.invoices_count, "corrections": sum(1 for r in rows if r["kind"] == "Correction")}
    return {"number": reg.number, "insurer": insurer.name, "tin": insurer.tin, "month": f"{reg.month:%Y-%m}", "invoices": t["invoices_count"], "lines": t["lines_count"],
            "insurer_total": t["insurer_total"], "patient_total": t["patient_total"], "payment_days": insurer.payment_days, "corrections": t["corrections"]}


def summary_of(rows: list[dict]) -> dict:
    out: dict[str, list] = {}
    for r in rows:
        a = out.setdefault(r["service"], [0, ZERO, ZERO])
        a[0] += r["qty"]
        a[1] += r["line_total"]
        a[2] += r["insurer_amount"]
    return out


def paid_total(db: Session, registry_id: uuid.UUID) -> Decimal:
    return Decimal(db.scalar(select(func.coalesce(func.sum(InsurerPayment.amount), 0)).where(InsurerPayment.registry_id == registry_id,
                                                                                             InsurerPayment.reversed_at.is_(None))))


def freeze(db: Session, reg: InsuranceRegistry, rows: list[dict], xlsx: bytes, key: str, by: uuid.UUID, now: datetime) -> None:
    """Qatorlarni qotirib, fayl ma'lumotlarini yozadi va holatni Sent ga o'tkazadi."""
    t = totals(rows)
    for r in rows:
        db.add(InsuranceRegistryLine(registry_id=reg.id, invoice_line_id=r["invoice_line_id"], kind=r["kind"], line_date=r["date"], invoice_number=r["invoice"],
                                     patient=r["patient"], policy=r["policy"], letter=r["letter"], contract=r["contract"], service=r["service"], qty=r["qty"],
                                     line_total=r["line_total"], insurer_amount=r["insurer_amount"], patient_amount=r["patient_amount"], branch=r["branch"], created_by=by))
    reg.insurer_total, reg.patient_total, reg.lines_count, reg.invoices_count = t["insurer_total"], t["patient_total"], t["lines_count"], t["invoices_count"]
    reg.file_key, reg.file_name, reg.file_size, reg.file_sha256 = key, f"{reg.number}.xlsx", len(xlsx), hashlib.sha256(xlsx).hexdigest()
    reg.status, reg.sent_at, reg.sent_by = "Sent", now, by
    db.flush()


def xlsx_of(db: Session, reg: InsuranceRegistry, rows: list[dict]) -> bytes:
    return ins.registry_xlsx(db, head_of(db, reg, rows), rows, summary_of(rows), reg.branch_id)
