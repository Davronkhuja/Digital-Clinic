"""Dashboard va tahlil: barcha raqamlar bazadan hisoblanadi."""
from collections import Counter
from datetime import date, timedelta

from sqlalchemy import Date, cast, func, select, true
from sqlalchemy.orm import Session

from app.models import Appointment, Encounter, Patient, Staff, Transaction
from app.schemas.enums import AppointmentStatus, GenderEnum, StaffRole, StatusEnum, TransactionType
from app.services.periods import CLINIC_TZ, clinic_today, pct_change, previous_window, window

WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
AGE_GROUPS = [("0-17", 0, 17), ("18-35", 18, 35), ("36-55", 36, 55), ("56-70", 56, 70), ("70+", 71, 200)]


def _between(column, start: date | None, end: date):
    """Davr sharti; start=None ('all') bo'lsa chegarasiz (kelajakdagi rejalashtirilgan qabullar ham kiradi)."""
    return column.between(start, end) if start else true()


def _income(db: Session, start: date | None, end: date) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.deleted_at.is_(None), Transaction.type == TransactionType.income,
            _between(Transaction.date, start, end))
    )
    return float(total)


def _expense(db: Session, start: date | None, end: date) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.deleted_at.is_(None), Transaction.type == TransactionType.expense,
            _between(Transaction.date, start, end))
    )
    return float(total)


def _appointments(db: Session, start: date | None, end: date) -> int:
    return db.scalar(select(func.count()).select_from(Appointment).where(_between(Appointment.date, start, end)))


def _new_patients(db: Session, start: date | None, end: date) -> int:
    created = cast(func.timezone(str(CLINIC_TZ), Patient.created_at), Date)
    return db.scalar(select(func.count()).select_from(Patient).where(_between(created, start, end)))


def _months_back(today: date, n: int) -> list[date]:
    """Oxirgi n ta oyning 1-sanalari (eskidan yangiga)."""
    year, month = today.year, today.month
    months = []
    for _ in range(n):
        months.append(date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))


def _monthly(db: Session, model, date_col, value, where, today: date, n: int = 6) -> list[dict]:
    months = _months_back(today, n)
    month_col = func.date_trunc("month", date_col)
    rows = db.execute(
        select(cast(month_col, Date), value).where(where, date_col >= months[0]).group_by(month_col)
    ).all()
    by_month = {m: v for m, v in rows}
    return [{"month": m.strftime("%Y-%m"), "value": float(by_month.get(m, 0))} for m in months]


def dashboard(db: Session, period: str, today: date | None = None) -> dict:
    today = today or clinic_today()
    start, end = window(period, today)
    prev = previous_window(period, today)

    revenue = _income(db, start, end)
    appts = _appointments(db, start, end)
    new_patients = _new_patients(db, start, end)
    changes = {"revenue": None, "appointments": None, "new_patients": None}
    if prev:
        changes = {
            "revenue": pct_change(revenue, _income(db, *prev)),
            "appointments": pct_change(appts, _appointments(db, *prev)),
            "new_patients": pct_change(new_patients, _new_patients(db, *prev)),
        }

    revenue_chart = _monthly(
        db, Transaction, Transaction.date, func.coalesce(func.sum(Transaction.amount), 0),
        (Transaction.deleted_at.is_(None)) & (Transaction.type == TransactionType.income), today)

    # Oxirgi 7 kun: yangi bemorlar (shu kuni ro'yxatdan o'tgan) va qaytganlar (oldin ro'yxatdan o'tib, shu kuni qabul qilingan)
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    created = cast(func.timezone(str(CLINIC_TZ), Patient.created_at), Date)
    new_by_day = dict(db.execute(
        select(created, func.count()).where(created >= days[0]).group_by(created)).all())
    returning_rows = db.execute(
        select(Appointment.date, func.count(func.distinct(Appointment.patient_id)))
        .join(Patient, Appointment.patient_id == Patient.id)
        .where(Appointment.date >= days[0], Appointment.date <= today,
               Appointment.status.in_([AppointmentStatus.completed, AppointmentStatus.scheduled]),
               created < Appointment.date)
        .group_by(Appointment.date)).all()
    returning_by_day = dict(returning_rows)
    patient_flow = [{"day": WEEKDAYS[d.weekday()], "date": d.isoformat(),
                     "new": new_by_day.get(d, 0), "returning": returning_by_day.get(d, 0)} for d in days]

    return {
        "period": period,
        "from": start.isoformat() if start else None,
        "to": end.isoformat(),
        "total_patients": db.scalar(select(func.count()).select_from(Patient)),
        "new_patients": new_patients,
        "appointments_today": db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.date == today, Appointment.status != AppointmentStatus.cancelled)),
        "appointments": appts,
        "revenue": revenue,
        "expense": _expense(db, start, end),
        "active_doctors": db.scalar(
            select(func.count()).select_from(Staff).where(Staff.role == StaffRole.doctor, Staff.status == StatusEnum.active)),
        "changes": changes,
        "revenue_chart": revenue_chart,
        "patient_flow": patient_flow,
    }


def reports(db: Session, period: str, today: date | None = None) -> dict:
    today = today or clinic_today()
    start, end = window(period, today)

    top_diagnoses = [
        {"name": name, "count": n}
        for name, n in db.execute(
            select(Encounter.diagnosis, func.count().label("n"))
            .where(Encounter.deleted_at.is_(None), _between(Encounter.visit_date, start, end))
            .group_by(Encounter.diagnosis).order_by(func.count().desc(), Encounter.diagnosis).limit(5)).all()
    ]

    top_doctors = [
        {"name": name, "department": dept, "patients": patients, "appointments": n}
        for name, dept, patients, n in db.execute(
            select(Staff.full_name, Staff.department, func.count(func.distinct(Appointment.patient_id)), func.count())
            .select_from(Appointment)
            .join(Staff, Appointment.doctor_id == Staff.id)
            .where(Appointment.status == AppointmentStatus.completed, _between(Appointment.date, start, end))
            .group_by(Staff.id).order_by(func.count().desc(), Staff.full_name).limit(5)).all()
    ]

    status_counts = {s.value: 0 for s in AppointmentStatus}
    for status, n in db.execute(
        select(Appointment.status, func.count()).where(_between(Appointment.date, start, end)).group_by(Appointment.status)
    ).all():
        status_counts[status.value] = n
    total_appts = sum(status_counts.values())

    dept_rows = db.execute(
        select(func.coalesce(Staff.department, "—"), func.count())
        .select_from(Appointment)
        .join(Staff, Appointment.doctor_id == Staff.id)
        .where(_between(Appointment.date, start, end)).group_by(Staff.department).order_by(func.count().desc())).all()
    departments = [{"name": name, "count": n, "pct": round(n / total_appts * 100, 1)} for name, n in dept_rows]

    gender = {g.value: 0 for g in GenderEnum}
    for g, n in db.execute(select(Patient.gender, func.count()).group_by(Patient.gender)).all():
        gender[g.value] = n
    ages = Counter()
    unknown = 0
    for (birth,) in db.execute(select(Patient.birth_date)).all():
        if not birth:
            unknown += 1
            continue
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        label = next(label for label, lo, hi in AGE_GROUPS if lo <= age <= hi)
        ages[label] += 1
    total_patients = sum(gender.values())

    return {
        "period": period,
        "from": start.isoformat() if start else None,
        "to": end.isoformat(),
        "top_diagnoses": top_diagnoses,
        "top_doctors": top_doctors,
        "appointment_statuses": status_counts,
        "departments": departments,
        "monthly_appointments": _monthly(
            db, Appointment, Appointment.date, func.count(), Appointment.status != AppointmentStatus.cancelled, today),
        "patient_demographics": {
            "total": total_patients,
            "gender": gender,
            "age_groups": [{"label": label, "count": ages[label],
                            "pct": round(ages[label] / total_patients * 100, 1) if total_patients else 0}
                           for label, _, _ in AGE_GROUPS],
            "unknown_age": unknown,
        },
    }


def insights(db: Session, today: date | None = None) -> list[dict]:
    """Klinika ma'lumotlaridan hosil bo'lgan tavsiyalar (qattiq yozilgan matn emas)."""
    today = today or clinic_today()
    start, end = window("month", today)
    stats = reports(db, "month", today)
    out: list[dict] = []
    statuses = stats["appointment_statuses"]
    total = sum(statuses.values())
    if total:
        lost = statuses[AppointmentStatus.cancelled.value] + statuses[AppointmentStatus.no_show.value]
        rate = round(lost / total * 100, 1)
        kind = "warning" if rate >= 15 else "info"
        out.append({"type": kind, "title": "Bekor qilingan va kelmagan qabullar",
                    "message": f"Oxirgi 30 kunda uchrashuvlarning {rate}% i bekor qilindi yoki bemor kelmadi ({lost}/{total})."})
    prev = previous_window("month", today)
    cur, before = _income(db, start, end), _income(db, *prev)
    change = pct_change(cur, before)
    if change is not None:
        out.append({"type": "success" if change >= 0 else "warning", "title": "Daromad dinamikasi",
                    "message": f"Oxirgi 30 kun daromadi oldingi 30 kunga nisbatan {change:+.1f}% ga o'zgardi."})
    dow = db.execute(
        select(func.extract("isodow", Appointment.date).label("d"), func.count())
        .where(Appointment.date.between(today - timedelta(days=89), today), Appointment.status != AppointmentStatus.cancelled)
        .group_by("d").order_by(func.count().desc()).limit(1)).first()
    if dow:
        out.append({"type": "info", "title": "Eng band kun",
                    "message": f"Oxirgi 90 kunda eng ko'p qabul haftaning {WEEKDAYS[int(dow[0]) - 1]} kuniga to'g'ri keldi ({dow[1]} ta)."})
    return out


def no_show_weekly(db: Session, weeks: int = 8, today: date | None = None) -> dict:
    """Haftalik kelmay qolish ulushi: no_show / (completed + no_show), eslatma yuborilgan va yuborilmagan qabullar kesimida.
    Hafta dushanbadan (klinika sanasi). Eslatma yuborilgan: shu qabuldan kamida bitta eslatma xabari `Sent`."""
    from sqlalchemy import exists

    from app.models import Message
    from app.schemas.enums import MessageStatus

    today = today or clinic_today()
    this_monday = today - timedelta(days=today.weekday())
    first = this_monday - timedelta(weeks=weeks - 1)
    reminded = exists().where(
        Message.appointment_id == Appointment.id, Message.kind.like("reminder%"), Message.status == MessageStatus.sent)
    rows = db.execute(
        select(Appointment.date, Appointment.status, reminded.label("reminded"))
        .where(Appointment.date >= first, Appointment.date < this_monday + timedelta(days=7),
               Appointment.status.in_([AppointmentStatus.completed, AppointmentStatus.no_show]))
    ).all()
    buckets: dict[date, dict] = {
        first + timedelta(weeks=i): {"total": 0, "no_show": 0, "reminded": [0, 0], "not_reminded": [0, 0]} for i in range(weeks)}
    for day, status, was_reminded in rows:
        b = buckets[day - timedelta(days=day.weekday())]
        miss = status == AppointmentStatus.no_show
        b["total"] += 1
        b["no_show"] += miss
        group = b["reminded" if was_reminded else "not_reminded"]
        group[0] += 1
        group[1] += miss

    def rate(miss: int, total: int) -> float | None:
        return round(miss * 100 / total, 1) if total else None

    def group(g: list) -> dict:
        return {"total": g[0], "no_show": g[1], "rate": rate(g[1], g[0])}

    out = [{"week_start": w.isoformat(), "total": b["total"], "no_show": b["no_show"], "rate": rate(b["no_show"], b["total"]),
            "reminded": group(b["reminded"]), "not_reminded": group(b["not_reminded"])} for w, b in sorted(buckets.items())]
    return {"weeks": out, "current": out[-1]}
