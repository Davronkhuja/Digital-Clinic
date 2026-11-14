# ruff: noqa: E501
"""Tahliliy hisobotlar (v1.9.23): daromad, bemor oqimi, shifokor yuklamasi, kelmay qolish. Hammasi bazadan, davr va filial bo'yicha.
Bir tuzilma ({title, period, scope, sections:[{title, columns, rows, totals}]}) JSON, Excel va PDF'ga chiqadi."""
import io
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import Date, cast, exists, func, select
from sqlalchemy.orm import Session

from app.models import Appointment, Branch, Invoice, InvoiceLine, Message, Patient, Payment, PaymentRefund, Staff
from app.schemas.enums import AppointmentStatus, InvoiceStatus, MessageStatus, PaymentStatus
from app.services import availability
from app.services.exports import XLSX, period
from app.services.money import q2
from app.services.periods import CLINIC_TZ

KINDS = {
    "revenue": "Daromad hisoboti",
    "patient_flow": "Bemorlar oqimi",
    "doctor_load": "Shifokor yuklamasi",
    "no_show": "Kelmay qolish hisoboti",
}
ZERO = Decimal("0.00")


def _day(column):
    return cast(func.timezone(str(CLINIC_TZ), column), Date)


def _sec(title: str, columns: list[str], rows: list[list], totals: list | None = None) -> dict:
    return {"title": title, "columns": columns, "rows": rows, "totals": totals}


def _days(d_from: date, d_to: date):
    d = d_from
    while d <= d_to:
        yield d
        d += timedelta(days=1)


def revenue(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    pday = _day(Payment.paid_at)
    refunded = select(func.coalesce(func.sum(PaymentRefund.amount), 0)).where(PaymentRefund.payment_id == Payment.id).scalar_subquery()
    pstmt = select(pday, Payment.method, Payment.amount, refunded).where(Payment.status == PaymentStatus.paid, pday >= d_from, pday <= d_to)
    if branch_id:
        pstmt = pstmt.where(Payment.branch_id == branch_id)
    by_day: dict[date, list] = defaultdict(lambda: [0, ZERO, ZERO])
    by_method: dict[str, list] = defaultdict(lambda: [0, ZERO, ZERO])
    for d, method, amount, ref in db.execute(pstmt).all():
        for acc in (by_day[d], by_method[method.value]):
            acc[0] += 1
            acc[1] += amount
            acc[2] += ref
    days = [[d.isoformat(), v[0], v[1], v[2], v[1] - v[2]] for d, v in sorted(by_day.items())]
    methods = [[m, v[0], v[1], v[2], v[1] - v[2]] for m, v in sorted(by_method.items())]
    tot = lambda rows: ["Jami", sum(r[1] for r in rows), sum((r[2] for r in rows), ZERO), sum((r[3] for r in rows), ZERO), sum((r[4] for r in rows), ZERO)]  # noqa: E731
    iday = _day(Invoice.issued_at)
    sstmt = (select(InvoiceLine.name, func.sum(InvoiceLine.quantity), func.sum(InvoiceLine.net_total), func.sum(InvoiceLine.vat_amount))
             .join(Invoice, InvoiceLine.invoice_id == Invoice.id)
             .where(Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partially_paid, InvoiceStatus.paid]), iday >= d_from, iday <= d_to)
             .group_by(InvoiceLine.name).order_by(func.sum(InvoiceLine.net_total).desc()))
    if branch_id:
        sstmt = sstmt.where(Invoice.branch_id == branch_id)
    services = [[n, int(q), t, v] for n, q, t, v in db.execute(sstmt).all()]
    return [
        _sec("Kunlar bo'yicha (to'lovlar)", ["Sana", "To'lovlar soni", "Yig'ilgan", "Qaytarilgan", "Sof"], days, tot(days) if days else None),
        _sec("To'lov usuli bo'yicha", ["Usul", "To'lovlar soni", "Yig'ilgan", "Qaytarilgan", "Sof"], methods, tot(methods) if methods else None),
        _sec("Xizmatlar bo'yicha (hisob-fakturalar)", ["Xizmat", "Soni", "Summa", "shundan QQS"], services,
             ["Jami", sum(r[1] for r in services), sum((r[2] for r in services), ZERO), sum((r[3] for r in services), ZERO)] if services else None),
    ]


def patient_flow(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    created = _day(Patient.created_at)
    nstmt = select(created, Patient.source).where(created >= d_from, created <= d_to)
    if branch_id:
        nstmt = nstmt.where(Patient.branch_id == branch_id)
    new_by_day: dict[date, int] = defaultdict(int)
    sources: dict[str, int] = defaultdict(int)
    for d, src in db.execute(nstmt).all():
        new_by_day[d] += 1
        sources[src or "ko'rsatilmagan"] += 1
    vstmt = (select(Appointment.date, Appointment.patient_id, created).join(Patient, Appointment.patient_id == Patient.id)
             .where(Appointment.status == AppointmentStatus.completed, Appointment.date >= d_from, Appointment.date <= d_to))
    if branch_id:
        vstmt = vstmt.where(Appointment.branch_id == branch_id)
    visits: dict[date, list] = defaultdict(lambda: [0, set(), set()])
    for d, pid, reg in db.execute(vstmt).all():
        v = visits[d]
        v[0] += 1
        v[1].add(pid)
        if reg < d:
            v[2].add(pid)                                  # oldin ro'yxatdan o'tgan (qaytgan) bemor
    rows = []
    for d in _days(d_from, d_to):
        v = visits.get(d, [0, set(), set()])
        if new_by_day.get(d) or v[0]:
            rows.append([d.isoformat(), new_by_day.get(d, 0), v[0], len(v[1]), len(v[2])])
    totals = ["Jami", sum(r[1] for r in rows), sum(r[2] for r in rows), sum(r[3] for r in rows), sum(r[4] for r in rows)] if rows else None
    src_rows = [[k, v] for k, v in sorted(sources.items(), key=lambda kv: -kv[1])]
    return [
        _sec("Kunlar bo'yicha", ["Sana", "Yangi bemorlar", "Tashriflar (yakunlangan)", "Noyob bemorlar", "Qaytgan bemorlar"], rows, totals),
        _sec("Yangi bemorlar manbasi", ["Manba", "Bemorlar"], src_rows, ["Jami", sum(r[1] for r in src_rows)] if src_rows else None),
    ]


def doctor_load(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    stmt = (select(Staff.id, Staff.full_name, Staff.department, Appointment.status, func.count(), func.coalesce(func.sum(
        func.extract("epoch", Appointment.ends_at - Appointment.starts_at) / 60), 0))
        .join(Staff, Appointment.doctor_id == Staff.id).where(Appointment.date >= d_from, Appointment.date <= d_to)
        .group_by(Staff.id, Staff.full_name, Staff.department, Appointment.status))
    if branch_id:
        stmt = stmt.where(Appointment.branch_id == branch_id)
    docs: dict = {}
    for sid, name, dept, status, n, minutes in db.execute(stmt).all():
        d = docs.setdefault(sid, {"name": name, "dept": dept or "—", "counts": defaultdict(int), "busy": 0})
        d["counts"][status] += n
        if status in (AppointmentStatus.scheduled, AppointmentStatus.completed):
            d["busy"] += float(minutes)
    rows = []
    for sid, d in sorted(docs.items(), key=lambda kv: kv[1]["name"]):
        c = d["counts"]
        done, miss = c[AppointmentStatus.completed], c[AppointmentStatus.no_show]
        avail = None
        if branch_id:                                       # ish soati: filial jadvalidan (shablonsiz shifokor uchun noma'lum)
            avail = sum(sum((we - ws).total_seconds() / 60 for ws, we in availability.day_windows(db, sid, day, branch_id)) for day in _days(d_from, d_to))
            if avail >= 24 * 60 * ((d_to - d_from).days + 1) - 1:
                avail = None                                # cheklovsiz kun (jadval yo'q)
        rows.append([d["name"], d["dept"], sum(c.values()), done, c[AppointmentStatus.scheduled], miss, c[AppointmentStatus.cancelled],
                     round(miss * 100 / (done + miss), 1) if done + miss else None, round(d["busy"] / 60, 1), round(avail / 60, 1) if avail else None,
                     round(d["busy"] * 100 / avail, 1) if avail else None])
    totals = ["Jami", "", sum(r[2] for r in rows), sum(r[3] for r in rows), sum(r[4] for r in rows), sum(r[5] for r in rows), sum(r[6] for r in rows), None,
              round(sum(r[8] for r in rows), 1), None, None] if rows else None
    return [_sec("Shifokorlar bo'yicha", ["Shifokor", "Bo'lim", "Jami qabul", "Yakunlangan", "Rejalashtirilgan", "Kelmagan", "Bekor qilingan", "Kelmay qolish %",
                                          "Band soat", "Ish soati (jadval)", "Yuklama %"], rows, totals)]


def no_show(db: Session, branch_id, d_from: date, d_to: date) -> list[dict]:
    reminded = exists().where(Message.appointment_id == Appointment.id, Message.kind.like("reminder%"), Message.status == MessageStatus.sent)
    stmt = (select(Appointment.date, Staff.full_name, Appointment.status, reminded.label("reminded")).join(Staff, Appointment.doctor_id == Staff.id)
            .where(Appointment.status.in_([AppointmentStatus.completed, AppointmentStatus.no_show]), Appointment.date >= d_from, Appointment.date <= d_to))
    if branch_id:
        stmt = stmt.where(Appointment.branch_id == branch_id)
    weeks: dict[date, list] = defaultdict(lambda: [0, 0])
    doctors: dict[str, list] = defaultdict(lambda: [0, 0])
    groups = {True: [0, 0], False: [0, 0]}
    for d, name, status, was in db.execute(stmt).all():
        miss = 1 if status == AppointmentStatus.no_show else 0
        wk = d - timedelta(days=d.weekday())
        for acc in (weeks[wk], doctors[name], groups[bool(was)]):
            acc[0] += 1
            acc[1] += miss
    pct = lambda a: round(a[1] * 100 / a[0], 1) if a[0] else None  # noqa: E731
    wrows = [[k.isoformat(), v[0], v[1], pct(v)] for k, v in sorted(weeks.items())]
    drows = [[k, v[0], v[1], pct(v)] for k, v in sorted(doctors.items())]
    grows = [["Eslatma yuborilgan", *groups[True], pct(groups[True])], ["Eslatma yuborilmagan", *groups[False], pct(groups[False])]]
    allv = [sum(v[0] for v in groups.values()), sum(v[1] for v in groups.values())]
    return [
        _sec("Haftalar bo'yicha (dushanbadan)", ["Hafta", "Qabullar", "Kelmagan", "Kelmay qolish %"], wrows, ["Jami", *allv, pct(allv)] if wrows else None),
        _sec("Eslatma kesimida", ["Guruh", "Qabullar", "Kelmagan", "Kelmay qolish %"], grows),
        _sec("Shifokorlar bo'yicha", ["Shifokor", "Qabullar", "Kelmagan", "Kelmay qolish %"], drows),
    ]


BUILDERS = {"revenue": revenue, "patient_flow": patient_flow, "doctor_load": doctor_load, "no_show": no_show}


def build(db: Session, kind: str, branch_id, d_from: date | None, d_to: date | None) -> dict:
    if kind not in BUILDERS:
        raise HTTPException(404, "Hisobot turi topilmadi")
    start, end = period(d_from, d_to)
    scope = db.scalar(select(Branch.name).where(Branch.id == branch_id)) if branch_id else "Hamma filial"
    return {"kind": kind, "title": KINDS[kind], "from": start.isoformat(), "to": end.isoformat(), "scope": scope, "generated_at": datetime.now(CLINIC_TZ).strftime("%Y-%m-%d %H:%M"),
            "sections": BUILDERS[kind](db, branch_id, start, end)}


# ---------- Render ----------

def _num(v):
    return float(v) if isinstance(v, Decimal) else v


def to_xlsx(report: dict) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Hisobot"
    ws0.append([report["title"]])
    ws0["A1"].font = Font(bold=True, size=14)
    ws0.append(["Davr", f"{report['from']} - {report['to']}"])
    ws0.append(["Filial", report["scope"]])
    ws0.append(["Tayyorlangan", report["generated_at"]])
    ws0.column_dimensions["A"].width = 18
    ws0.column_dimensions["B"].width = 34
    for s in report["sections"]:
        ws = wb.create_sheet(s["title"][:31].replace("/", "-"))
        ws.append(s["columns"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in s["rows"]:
            ws.append([_num(v) for v in r])
        if s["totals"]:
            ws.append([_num(v) for v in s["totals"]])
            for c in ws[ws.max_row]:
                c.font = Font(bold=True)
        for i, col in enumerate(s["columns"], 1):
            ws.column_dimensions[get_column_letter(i)].width = max(14, min(len(col) + 4, 40))
        ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def to_pdf(report: dict) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

    from app.services.pdf import _fonts, _p

    regular, bold = _fonts()
    base = ParagraphStyle("base", fontName=regular, fontSize=8.5, leading=10.5)
    strong = ParagraphStyle("strong", parent=base, fontName=bold)
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=15, leading=19)
    small = ParagraphStyle("small", parent=base, fontSize=8, textColor=colors.HexColor("#64748b"))
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm, title=report["title"])
    story = [_p(report["title"], title), _p(f"Davr: {report['from']} - {report['to']} · {report['scope']} · {report['generated_at']}", small), Spacer(1, 5 * mm)]

    def fmt(v):
        if v is None:
            return "—"
        if isinstance(v, (Decimal, float)) and not isinstance(v, bool):
            return f"{v:,.2f}".replace(",", " ") if abs(v) >= 1000 or isinstance(v, Decimal) else f"{v:g}"
        return str(v)

    for s in report["sections"]:
        story.append(_p(s["title"], ParagraphStyle("h", parent=strong, fontSize=11, leading=14)))
        story.append(Spacer(1, 2 * mm))
        data = [[_p(c, strong) for c in s["columns"]]] + [[_p(fmt(v), base) for v in r] for r in s["rows"]]
        if s["totals"]:
            data.append([_p(fmt(v), strong) for v in s["totals"]])
        if len(data) == 1:
            story.append(_p("Ma'lumot yo'q", small))
        else:
            t = Table(data, repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
            story.append(t)
        story.append(Spacer(1, 6 * mm))
    doc.build(story)
    return buf.getvalue()


__all__ = ["KINDS", "XLSX", "build", "q2", "to_pdf", "to_xlsx"]
