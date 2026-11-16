# ruff: noqa: E501
"""Tuzilmali JSON log (PII'siz). Jurnalga so'rov matni, query, sarlavha va shaxsiy ma'lumot yozilmaydi: faqat usul, marshrut SHABLONI,
status, vaqt, so'rov ID. Qo'shimcha himoya: har qanday log xabaridagi email, telefon, uzun raqamlar (PINFL) va tokenlar yashiriladi."""
import json
import logging
import re
import sys
from datetime import UTC, datetime

from app.core.config import settings

_PII = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"eyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{4,}"), "[token]"),                      # JWT
    (re.compile(r"\+\d[\d\s().-]{7,}\d"), "[number]"),                                  # +998 ... telefon
    (re.compile(r"\b\d{9,}\b"), "[number]"),                                          # PINFL, telefon, hisob raqamlari
]
_STD = set(vars(logging.LogRecord("x", 0, "x", 0, "", (), None))) | {"message", "asctime", "taskName"}


def redact(text: str) -> str:
    for rx, repl in _PII:
        text = rx.sub(repl, text)
    return text


class PiiFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"), "level": record.levelname, "logger": record.name,
               "msg": record.getMessage()}
        out.update({k: v for k, v in record.__dict__.items() if k not in _STD and not k.startswith("_")})
        if record.exc_info:
            out["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(out, ensure_ascii=False, default=str)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(PiiFilter())
    handler.setFormatter(JsonFormatter() if settings.json_logs else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level.upper())
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "celery", "celery.app.trace", "celery.worker"):   # o'z handlerlarini olib tashlaymiz
        lg = logging.getLogger(name)
        lg.handlers, lg.propagate = [], True
