"""Pul: bazada numeric(14,2) (Decimal), tashqi to'lov tizimlarida tiyin (butun son). O'tkazish FAQAT shu yerda:
Payme (tiyin) va Click (so'm, kasr) adapterlari `to_tiyin`/`from_tiyin`/`format_sum` dan foydalanadi, o'zlari hisoblamaydi."""
from decimal import ROUND_HALF_UP, Decimal

TIYIN = Decimal(100)
CENT = Decimal("0.01")


def q2(value: Decimal | int | str | float) -> Decimal:
    """Pulni 2 xonaga yaxlitlash (tijorat yaxlitlash). Float qabul qilinmaydi ishonchli deb: str orqali."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def to_tiyin(amount: Decimal | int | str) -> int:
    """so'm (Decimal) -> tiyin (int). Kasr tiyin bo'lmasligi shart: ValueError."""
    value = Decimal(str(amount)) * TIYIN
    if value != value.to_integral_value():
        raise ValueError(f"Summa tiyinga butun bo'lmaydi: {amount}")
    return int(value)


def from_tiyin(tiyin: int) -> Decimal:
    """tiyin (int) -> so'm (Decimal, 2 xona)."""
    if isinstance(tiyin, bool) or not isinstance(tiyin, int):
        raise ValueError("Tiyin butun son bo'lishi kerak")
    return (Decimal(tiyin) / TIYIN).quantize(CENT)


def format_sum(amount: Decimal) -> str:
    """Click uchun: so'm, 2 xona ('150000.00')."""
    return format(q2(amount), "f")
