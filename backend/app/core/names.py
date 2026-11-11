"""Ismni solishtirish uchun normallashtirish: kirill -> lotin (o'zbek translit), apostroflar, harf registri."""
import re

_APOSTROPHES = "ʻʼ'`’‘´′"
_APOS_RE = re.compile(f"[{re.escape(_APOSTROPHES)}]")

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "'", "ы": "i",
    "ь": "", "э": "e", "ю": "yu", "я": "ya",
    # o'zbek kirillida qo'shimcha harflar
    "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}
_VOWEL_Y = re.compile(r"(?<=[aeiou])y(?=[aeiou])")  # Abdullayev ~ Абдуллаев


def normalize_name(name: str | None) -> str:
    """'Абдуллаев Ўктам' va "Abdullayev O'ktam" bir xil kalitga keladi: 'abdullaev o'ktam'."""
    text = _APOS_RE.sub("'", (name or "").lower())
    text = "".join(_CYR.get(ch, ch) for ch in text)
    text = _VOWEL_Y.sub("", text)
    return re.sub(r"\s+", " ", text).strip()
