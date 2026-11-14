# ruff: noqa: E501
"""Buxgalteriya (1C) uchun universal eksport: sotuvlar (xizmat bo'yicha), to'lovlar (usul bo'yicha), kassa smenalari, ombor harakatlari, shifokor foizlari.
Rasmiy 1C format hujjati yo'q: ustun nomlari, tartibi, sana/o'nlik/CSV ajratgichi Sozlamalarda tahrirlanadi (keyin buxgalter bilan moslanadi)."""
import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models import (
    Branch,
    CashShift,
    CommissionEntry,
    ExportColumn,
    ExportFormat,
    Invoice,
    InvoiceLine,
    Patient,
    Payment,
    PaymentRefund,
    Service,
    Staff,
    StockBatch,
    StockItem,
    StockMovement,
    User,
)
from app.schemas.enums import InvoiceStatus, PaymentStatus
from app.services import shifts
from app.services.money import q2
from app.services.periods import CLINIC_TZ, clinic_today

MAX_ROWS = 200_000
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Col:
    key: str
    header: str
    kind: str = "text"          # text | date | datetime | int | money | qty


@dataclass
class Dataset:
    name: str
    title: str
    columns: list[Col]
    query: Callable
    summary: Callable | None = None


def _day(column):
    return cast(func.timezone(str(CLINIC_TZ), column), Date)


def _local(dt: datetime | None) -> datetime | None:
    return dt.astimezone(CLINIC_TZ).replace(tzinfo=None) if dt else None


def _sales(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    day = _day(Invoice.issued_at)
    stmt = (select(InvoiceLine, Invoice, day, Patient.full_name, Staff.full_name, Branch.name)
            .join(Invoice, InvoiceLine.invoice_id == Invoice.id).join(Patient, Invoice.patient_id == Patient.id)
            .outerjoin(Staff, InvoiceLine.doctor_id == Staff.id).join(Branch, Invoice.branch_id == Branch.id)
            .where(Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partially_paid, InvoiceStatus.paid]), day >= d_from, day <= d_to)
            .order_by(Invoice.issued_at, Invoice.number, InvoiceLine.position))
    if branch_id:
        stmt = stmt.where(Invoice.branch_id == branch_id)
    return [{"date": d, "number": inv.number, "patient": patient, "service": ln.name, "mxik": ln.mxik, "package_code": ln.package_code,
             "qty": ln.quantity, "unit_price": ln.unit_price, "discount": ln.line_discount + ln.invoice_discount_share, "vat_percent": ln.vat_percent,
             "vat_amount": ln.vat_amount, "total": ln.net_total, "doctor": doctor, "status": inv.status.value, "branch": branch}
            for ln, inv, d, patient, doctor, branch in db.execute(stmt).all()]


def _sales_summary(rows: list[dict]) -> tuple[str, list[str], list[list]]:
    agg: dict[str, list] = {}
    for r in rows:
        a = agg.setdefault(r["service"], [0, Decimal(0), Decimal(0)])
        a[0] += r["qty"]
        a[1] += r["total"]
        a[2] += r["vat_amount"]
    return "Xizmat bo'yicha jami", ["Xizmat", "Soni", "Summa", "shundan QQS"], [[k, v[0], v[1], v[2]] for k, v in sorted(agg.items())]


def _payments(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    day = _day(Payment.paid_at)
    refunded = select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(PaymentRefund.payment_id == Payment.id).scalar_subquery()
    stmt = (select(Payment, day, refunded, Invoice.number, Patient.full_name, CashShift.z_number, Staff.full_name, Branch.name)
            .join(Invoice, Payment.invoice_id == Invoice.id).join(Patient, Invoice.patient_id == Patient.id).join(Branch, Payment.branch_id == Branch.id)
            .outerjoin(CashShift, Payment.shift_id == CashShift.id).outerjoin(User, Payment.created_by == User.id).outerjoin(Staff, User.staff_id == Staff.id)
            .where(Payment.status == PaymentStatus.paid, day >= d_from, day <= d_to).order_by(Payment.paid_at, Payment.id))
    if branch_id:
        stmt = stmt.where(Payment.branch_id == branch_id)
    return [{"date": d, "paid_at": _local(p.paid_at), "method": p.method.value, "amount": p.amount, "refunded": ref, "net": p.amount - ref, "invoice": num,
             "patient": patient, "receipt_id": p.receipt_id, "shift_z": z, "cashier": cashier, "branch": branch}
            for p, d, ref, num, patient, z, cashier, branch in db.execute(stmt).all()]


def _payments_summary(rows: list[dict]) -> tuple[str, list[str], list[list]]:
    agg: dict[str, list] = {}
    for r in rows:
        a = agg.setdefault(r["method"], [0, Decimal(0), Decimal(0)])
        a[0] += 1
        a[1] += r["amount"]
        a[2] += r["refunded"]
    return "Usul bo'yicha jami", ["Usul", "To'lovlar soni", "Summa", "Qaytarilgan", "Sof"], [[k, v[0], v[1], v[2], v[1] - v[2]] for k, v in sorted(agg.items())]


def _cash_shifts(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    day = _day(CashShift.opened_at)
    stmt = select(CashShift, Branch.name).join(Branch, CashShift.branch_id == Branch.id).where(day >= d_from, day <= d_to).order_by(CashShift.opened_at)
    if branch_id:
        stmt = stmt.where(CashShift.branch_id == branch_id)
    out = []
    for s, branch in db.execute(stmt).all():
        r = shifts.report(db, s)
        online = r["online"]["click"]["payments_total"] + r["online"]["payme"]["payments_total"]
        out.append({"z_number": s.z_number, "cashier": r["cashier"], "opened_at": _local(s.opened_at), "closed_at": _local(s.closed_at), "status": s.status.value,
                    "opening_cash": s.opening_cash, "cash_in": r["cash"]["payments_total"], "cash_refunds": r["cash"]["refunds_total"],
                    "card_in": r["card"]["payments_total"], "online_in": online, "withdrawals": r["withdrawals"]["total"], "payouts": r["payouts"]["total"],
                    "expected_cash": r["expected_cash"], "counted_cash": s.counted_cash, "difference": s.difference, "branch": branch})
    return out


def _stock(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    day = _day(StockMovement.created_at)
    stmt = (select(StockMovement, day, StockItem.name, StockItem.unit, StockBatch.batch_no, Branch.name, Staff.full_name)
            .join(StockItem, StockMovement.item_id == StockItem.id).join(StockBatch, StockMovement.batch_id == StockBatch.id)
            .join(Branch, StockMovement.branch_id == Branch.id).outerjoin(User, StockMovement.created_by == User.id).outerjoin(Staff, User.staff_id == Staff.id)
            .where(day >= d_from, day <= d_to).order_by(StockMovement.created_at, StockMovement.id))
    if branch_id:
        stmt = stmt.where(StockMovement.branch_id == branch_id)
    return [{"date": d, "at": _local(m.created_at), "kind": m.kind.value, "item": item, "unit": unit, "batch_no": batch, "qty": m.qty, "unit_cost": m.unit_cost,
             "amount": q2(m.qty * m.unit_cost), "reason": m.reason, "ref_type": m.ref_type, "by": by, "branch": branch}
            for m, d, item, unit, batch, branch, by in db.execute(stmt).all()]


def _commissions(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    stmt = (select(CommissionEntry, Staff.full_name, Service.name, Invoice.number, Branch.name)
            .join(Staff, CommissionEntry.doctor_id == Staff.id).join(Service, CommissionEntry.service_id == Service.id)
            .join(Payment, CommissionEntry.payment_id == Payment.id).join(Invoice, Payment.invoice_id == Invoice.id).join(Branch, Payment.branch_id == Branch.id)
            .where(CommissionEntry.entry_date >= d_from, CommissionEntry.entry_date <= d_to).order_by(CommissionEntry.entry_date, CommissionEntry.created_at))
    if branch_id:
        stmt = stmt.where(Payment.branch_id == branch_id)
    return [{"date": e.entry_date, "doctor": doctor, "kind": e.kind.value, "service": service, "invoice": number, "rule_kind": e.rule_kind.value,
             "base_kind": e.base_kind.value if e.base_kind else None, "base_amount": e.base_amount, "percent": e.rule_percent, "fixed": e.rule_fixed,
             "amount": e.amount, "settled": "Ha" if e.settlement_id else "Yo'q", "branch": branch}
            for e, doctor, service, number, branch in db.execute(stmt).all()]


DATASETS: dict[str, Dataset] = {d.name: d for d in (
    Dataset("sales", "Sotuvlar (xizmat bo'yicha)", [
        Col("date", "Sana", "date"), Col("number", "Hisob-faktura"), Col("patient", "Bemor"), Col("service", "Xizmat"), Col("mxik", "MXIK"),
        Col("package_code", "Qadoq kodi"), Col("qty", "Soni", "int"), Col("unit_price", "Narx", "money"), Col("discount", "Chegirma", "money"),
        Col("vat_percent", "QQS %", "money"), Col("vat_amount", "QQS summasi", "money"), Col("total", "Summa", "money"), Col("doctor", "Shifokor"),
        Col("status", "Holat"), Col("branch", "Filial")], _sales, _sales_summary),
    Dataset("payments", "To'lovlar (usul bo'yicha)", [
        Col("date", "Sana", "date"), Col("paid_at", "To'langan vaqt", "datetime"), Col("method", "Usul"), Col("amount", "Summa", "money"),
        Col("refunded", "Qaytarilgan", "money"), Col("net", "Sof", "money"), Col("invoice", "Hisob-faktura"), Col("patient", "Bemor"),
        Col("receipt_id", "Fiskal chek"), Col("shift_z", "Smena (Z)"), Col("cashier", "Kassir"), Col("branch", "Filial")], _payments, _payments_summary),
    Dataset("cash_shifts", "Kassa smenalari", [
        Col("z_number", "Z-raqam"), Col("cashier", "Kassir"), Col("opened_at", "Ochilgan", "datetime"), Col("closed_at", "Yopilgan", "datetime"),
        Col("status", "Holat"), Col("opening_cash", "Boshlang'ich naqd", "money"), Col("cash_in", "Naqd kirim", "money"), Col("cash_refunds", "Naqd qaytarish", "money"),
        Col("card_in", "Karta kirim", "money"), Col("online_in", "Onlayn kirim", "money"), Col("withdrawals", "Inkassatsiya", "money"),
        Col("payouts", "Foiz to'lovi (naqd)", "money"), Col("expected_cash", "Kutilgan naqd", "money"), Col("counted_cash", "Sanalgan naqd", "money"),
        Col("difference", "Farq", "money"), Col("branch", "Filial")], _cash_shifts),
    Dataset("stock_movements", "Ombor harakatlari", [
        Col("date", "Sana", "date"), Col("at", "Vaqt", "datetime"), Col("kind", "Tur"), Col("item", "Material"), Col("unit", "Birlik"), Col("batch_no", "Partiya"),
        Col("qty", "Miqdor", "qty"), Col("unit_cost", "Narx", "money"), Col("amount", "Summa", "money"), Col("reason", "Sabab"), Col("ref_type", "Hujjat turi"),
        Col("by", "Kim"), Col("branch", "Filial")], _stock),
    Dataset("commissions", "Shifokor foizlari", [
        Col("date", "Sana", "date"), Col("doctor", "Shifokor"), Col("kind", "Tur"), Col("service", "Xizmat"), Col("invoice", "Hisob-faktura"),
        Col("rule_kind", "Qoida"), Col("base_kind", "Asos"), Col("base_amount", "Asos summa", "money"), Col("percent", "Foiz", "money"), Col("fixed", "Qat'iy summa", "money"),
        Col("amount", "Foiz summasi", "money"), Col("settled", "Hisob-kitob qilingan"), Col("branch", "Filial")], _commissions),
)}


# ---------- Sozlamalar ----------

def get_format(db: Session) -> ExportFormat:
    row = db.scalar(select(ExportFormat).limit(1))
    return row or ExportFormat(date_format="iso", decimal_separator=".", csv_delimiter=";")


def effective_columns(db: Session, dataset: Dataset) -> list[tuple[Col, str, bool]]:
    """(ustun, sarlavha, yoqilgan) tartib bo'yicha: Sozlamadagi xarita, bo'lmasa standart."""
    rows = {r.key: r for r in db.scalars(select(ExportColumn).where(ExportColumn.dataset == dataset.name))}
    default = {c.key: c for c in dataset.columns}
    if not rows:
        return [(c, c.header, True) for c in dataset.columns]
    ordered = sorted((r for r in rows.values() if r.key in default), key=lambda r: (r.position, r.key))
    out = [(default[r.key], r.header, r.enabled) for r in ordered]
    out += [(c, c.header, False) for c in dataset.columns if c.key not in rows]       # keyin qo'shilgan ustunlar o'chiq
    return out


def save_columns(db: Session, dataset: Dataset, items: list[dict], actor) -> None:
    keys = {c.key for c in dataset.columns}
    seen: set[str] = set()
    for it in items:
        if it["key"] not in keys:
            raise HTTPException(422, f"Noma'lum ustun: {it['key']}")
        if it["key"] in seen:
            raise HTTPException(422, f"Ustun takrorlangan: {it['key']}")
        seen.add(it["key"])
    headers = [it["header"].strip().lower() for it in items if it["enabled"]]
    if not headers:
        raise HTTPException(422, "Kamida bitta ustun yoqilgan bo'lishi kerak")
    if len(set(headers)) != len(headers):
        raise HTTPException(422, "Yoqilgan ustunlar sarlavhalari takrorlanmasin")
    for r in db.scalars(select(ExportColumn).where(ExportColumn.dataset == dataset.name)):
        db.delete(r)
    db.flush()
    pos = 0
    for it in items:
        db.add(ExportColumn(dataset=dataset.name, key=it["key"], header=it["header"].strip(), position=pos, enabled=it["enabled"], created_by=actor))
        pos += 1
    for c in dataset.columns:                                                 # ro'yxatda yo'qlari o'chiq holda oxirida
        if c.key not in seen:
            db.add(ExportColumn(dataset=dataset.name, key=c.key, header=c.header, position=pos, enabled=False, created_by=actor))
            pos += 1


# ---------- Render ----------

def period(d_from: date | None, d_to: date | None) -> tuple[date, date]:
    end = d_to or clinic_today()
    start = d_from or end - timedelta(days=29)
    if start > end:
        raise HTTPException(422, "Boshlanish sanasi tugashdan keyin bo'lishi mumkin emas")
    if (end - start).days > 400:
        raise HTTPException(422, "Davr 400 kundan oshmasin")
    return start, end


def _csv_value(value, kind: str, fmt: ExportFormat) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M" if fmt.date_format == "dmy" else "%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y" if fmt.date_format == "dmy" else "%Y-%m-%d")
    if isinstance(value, bool):
        return "Ha" if value else "Yo'q"
    if isinstance(value, (Decimal, float)):
        text = f"{value:.3f}" if kind == "qty" else f"{Decimal(str(value)):.2f}"
        return text.rstrip("0").rstrip(".") if kind == "qty" and "." in text else text.replace(".", fmt.decimal_separator)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value                                                    # CSV/formula injection'dan himoya
    return str(value)


def _xlsx_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def render(db: Session, dataset: Dataset, rows: list[dict], file_format: str) -> tuple[bytes, str]:
    cols = [(c, h) for c, h, on in effective_columns(db, dataset) if on]
    fmt = get_format(db)
    if file_format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t" if fmt.csv_delimiter == "tab" else fmt.csv_delimiter, lineterminator="\r\n")
        writer.writerow([h for _, h in cols])
        for r in rows:
            writer.writerow([_csv_value(r.get(c.key), c.kind, fmt) for c, _ in cols])
        return ("﻿" + buf.getvalue()).encode("utf-8"), "text/csv; charset=utf-8"
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = dataset.title[:31].replace("/", "-")
    ws.append([h for _, h in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    date_fmt = "DD.MM.YYYY" if fmt.date_format == "dmy" else "YYYY-MM-DD"
    formats = {"date": date_fmt, "datetime": f"{date_fmt} HH:MM", "money": "#,##0.00", "qty": "#,##0.000", "int": "0"}
    for r in rows:
        ws.append([_xlsx_value(r.get(c.key)) for c, _ in cols])
    for idx, (c, h) in enumerate(cols, 1):
        letter = get_column_letter(idx)
        width = max([len(h)] + [len(str(ws.cell(row=i, column=idx).value or "")) for i in range(2, min(ws.max_row, 200) + 1)])
        ws.column_dimensions[letter].width = min(max(width + 2, 10), 50)
        if c.kind in formats:
            for i in range(2, ws.max_row + 1):
                ws.cell(row=i, column=idx).number_format = formats[c.kind]
    ws.freeze_panes = "A2"
    if dataset.summary:
        title, head, body = dataset.summary(rows)
        s2 = wb.create_sheet(title[:31])
        s2.append(head)
        for cell in s2[1]:
            cell.font = Font(bold=True)
        for line in body:
            s2.append([_xlsx_value(v) for v in line])
        for i in range(1, len(head) + 1):
            s2.column_dimensions[get_column_letter(i)].width = 22
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue(), XLSX
