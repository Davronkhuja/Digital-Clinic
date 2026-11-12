"""Fiskal chek adapteri (virtual kassa). Hozircha faqat `MockFiscalAdapter` (chek ID saqlanadi, tashqi so'rov yo'q).
Real operator (virtual kassa API) uchun hujjatlar va kalitlar kerak: ularsiz yozilmaydi, `FISCAL_BACKEND` boshqa qiymat RuntimeError.
Hamma summa TIYINda (butun son): so'm <-> tiyin faqat `services/money.py`."""
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import settings


class FiscalError(Exception):
    """Fiskal chek berilmadi (operator javob bermadi, rad etdi)."""


@dataclass
class FiscalResult:
    receipt_id: str
    fiscal_sign: str | None = None
    qr_url: str | None = None
    raw: dict = field(default_factory=dict)


class FiscalAdapter(Protocol):
    def sale(self, receipt: dict) -> FiscalResult: ...

    def refund(self, receipt: dict, original_receipt_id: str | None) -> FiscalResult: ...


class MockFiscalAdapter:
    """Test/demo: har chaqiruvga noyob `MOCK-...` chek ID; tashqi tarmoq yo'q."""

    def sale(self, receipt: dict) -> FiscalResult:
        return self._result("sale", receipt, None)

    def refund(self, receipt: dict, original_receipt_id: str | None) -> FiscalResult:
        return self._result("refund", receipt, original_receipt_id)

    @staticmethod
    def _result(kind: str, receipt: dict, original: str | None) -> FiscalResult:
        receipt_id = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        sign = hashlib.sha256(f"{receipt_id}:{receipt.get('total_tiyin')}".encode()).hexdigest()[:16].upper()
        return FiscalResult(receipt_id, sign, f"https://mock.fiscal.local/check/{receipt_id}",
                            {"kind": kind, "items": len(receipt.get("items", [])), "original": original})


_adapter: FiscalAdapter | None = None


def get_fiscal() -> FiscalAdapter:
    global _adapter
    if _adapter is None:
        if settings.fiscal_backend != "mock":
            raise RuntimeError(f"Noma'lum FISCAL_BACKEND: {settings.fiscal_backend} (hozircha faqat mock)")
        _adapter = MockFiscalAdapter()
    return _adapter
