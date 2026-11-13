"""OTP xavfsizligi (v1.8.12): production'da mock SMS taqiqlangan, kod oddiy jurnalga/bazaga yozilmaydi (faqat dev/test outbox),
5 daqiqalik muddat, 5 noto'g'ri urinishdan keyin blok, telefon va IP bo'yicha tezlik cheklovi."""
import json
import logging
import re
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, settings
from app.db.session import SessionLocal
from app.models import Message, OtpCode
from app.services import messaging

PHONE = "+998 90 777 10 01"
BASE = {"jwt_secret": "x" * 40, "database_url": "postgresql+psycopg://u:p@h/d"}


@pytest.fixture(autouse=True)
def _clear():
    messaging.MockSmsAdapter.SENT.clear()


def _request(client, phone=PHONE, **kw):
    return client.post("/public/otp/request", json={"phone": phone, "purpose": "portal", **kw})


def _code():
    return re.search(r"\b(\d{6})\b", messaging.MockSmsAdapter.SENT[-1][1]).group(1)


def _verify(client, code, phone=PHONE):
    return client.post("/public/otp/verify", json={"phone": phone, "purpose": "portal", "code": code})


def _wrong(code):
    return "000000" if code != "000000" else "111111"


def test_production_refuses_mock_sms(monkeypatch):
    with pytest.raises(ValidationError, match="SMS_BACKEND=mock"):
        Settings(_env_file=None, APP_ENV="production", sms_backend="mock", **BASE)
    with pytest.raises(ValidationError, match="MOCK_SMS_OUTBOX"):
        Settings(_env_file=None, ENV="production", sms_backend="provider", mock_sms_outbox="/tmp/x", **BASE)
    assert Settings(_env_file=None, sms_backend="mock", **BASE).is_production is False          # dev: mock ruxsat
    # ikkinchi himoya: ishlab turgan jarayonda ham adapter yuborishni rad etadi
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(messaging, "_adapters", {})
    with pytest.raises(RuntimeError, match="Production"):
        messaging.get_adapter(messaging.Channel.sms)
    with pytest.raises(RuntimeError, match="Production"):
        messaging.MockSmsAdapter().send("+998901112233", "Kod 123456")
    assert messaging.MockSmsAdapter.SENT == []


def test_code_is_not_in_normal_logs_nor_database_only_in_dev_outbox(client, caplog, tmp_path, monkeypatch):
    outbox = tmp_path / "sms.jsonl"
    monkeypatch.setattr(settings, "mock_sms_outbox", str(outbox))
    with caplog.at_level(logging.DEBUG):
        assert _request(client).status_code == 200
    code = _code()
    assert code not in caplog.text                                                   # oddiy jurnalda yo'q
    line = json.loads(outbox.read_text().splitlines()[-1])
    assert line["to"] == "+998907771001" and code in line["text"]                    # dev outbox'da bor
    assert oct(outbox.stat().st_mode & 0o777) == "0o600"
    with SessionLocal() as db:                                                       # bazada ham kod yo'q
        msg = db.scalar(select(Message).where(Message.kind == "otp"))
        assert code not in msg.body and msg.status.value == "Sent"
        assert code not in db.scalar(select(OtpCode.code_hash))                      # faqat xesh


def test_code_expires_after_five_minutes(client):
    from app.services import otp
    assert otp.CODE_TTL == timedelta(minutes=5)
    _request(client)
    code = _code()
    with SessionLocal() as db:
        row = db.scalar(select(OtpCode))
        assert timedelta(minutes=4, seconds=50) < row.expires_at - datetime.now(UTC) <= timedelta(minutes=5)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert _verify(client, code).status_code == 400                                  # muddati o'tgan kod to'g'ri bo'lsa ham yaroqsiz


def test_five_wrong_attempts_block_the_phone(client):
    _request(client)
    code = _code()
    for i in range(4):
        assert _verify(client, _wrong(code)).status_code == 400, i
    assert _verify(client, _wrong(code)).status_code == 429                          # 5-xato: blok
    assert _verify(client, code).status_code == 429                                  # to'g'ri kod ham o'tmaydi
    assert _request(client).status_code == 429                                       # yangi kod ham so'rab bo'lmaydi
    assert len(messaging.MockSmsAdapter.SENT) == 1
    assert _request(client, "+998 90 777 10 02").status_code == 200                  # boshqa telefonga ta'sir qilmaydi
    with SessionLocal() as db:                                                       # 15 daqiqadan keyin blok ochiladi
        from app.models import RateEvent
        for ev in db.scalars(select(RateEvent).where(RateEvent.key == "+998907771001")):
            ev.created_at = datetime.now(UTC) - timedelta(minutes=16)
        db.commit()
    assert _request(client).status_code == 200


def test_phone_and_ip_rate_limits(client):
    for _ in range(3):
        assert _request(client).status_code == 200
    assert _request(client).status_code == 429                                       # telefon: 15 daqiqada 3 ta
    assert len(messaging.MockSmsAdapter.SENT) == 3
    for i in range(7):                                                               # IP: soatiga 10 ta (3 ta sarflangan)
        assert _request(client, f"+998 90 777 20 {i:02d}").status_code == 200
    assert _request(client, "+998 90 777 20 99").status_code == 429
    assert len(messaging.MockSmsAdapter.SENT) == 10
    for _ in range(30):                                                              # tasdiqlash: IP bo'yicha soatiga 30 ta
        _verify(client, "123456", "+998 90 777 30 01")
    assert _verify(client, "123456", "+998 90 777 30 01").status_code == 429
