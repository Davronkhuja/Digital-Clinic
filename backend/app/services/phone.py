"""Telefon raqamini E.164 (O'zbekiston) ga keltirish: '+998 90 123-45-67', '90 123 45 67', '998901234567' -> '+998901234567'."""
import re


def normalize_phone(raw: str | None) -> str | None:
    """None: raqam yaroqsiz. Faqat O'zbekiston raqamlari (998 + 9 raqam)."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return None
