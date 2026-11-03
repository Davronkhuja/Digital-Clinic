"""Hisobot davrlari: oxirgi N kun (aylanma oyna), oldingi teng davr bilan solishtirish uchun."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("Asia/Tashkent")
PERIOD_DAYS = {"week": 7, "month": 30, "year": 365}


def clinic_today() -> date:
    return datetime.now(CLINIC_TZ).date()


def window(period: str, today: date | None = None) -> tuple[date | None, date]:
    """(boshlanish, tugash) — ikkalasi ham kiradi. 'all' uchun boshlanish None."""
    today = today or clinic_today()
    days = PERIOD_DAYS.get(period)
    return (today - timedelta(days=days - 1) if days else None), today


def previous_window(period: str, today: date | None = None) -> tuple[date, date] | None:
    start, _ = window(period, today)
    days = PERIOD_DAYS.get(period)
    if not start or not days:
        return None
    return start - timedelta(days=days), start - timedelta(days=1)


def pct_change(current: float, previous: float) -> float | None:
    """O'sish foizi; oldingi davr 0 bo'lsa solishtirib bo'lmaydi (None)."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)
