# ruff: noqa: E501
"""Operatsion endpointlar: /health (jarayon tirik), /ready (trafik qabul qilishga tayyor: baza), /metrics (token bilan)."""
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services import metrics

router = APIRouter()
log = logging.getLogger("app.ops")


@router.get("/health", tags=["Ops"], summary="Tirikligi (liveness)", description="Jarayon javob beradi. Bazaga murojaat qilmaydi.")
def health():
    return {"status": "ok"}


@router.get("/ready", tags=["Ops"], summary="Tayyorligi (readiness)",
            description="Baza ishlayotgan bo'lsa 200, aks holda 503. Redis (xabarlar navbati) ishlamasa API ishlashda davom etadi: `redis` maydonida ko'rsatiladi.")
def ready(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        log.error("Baza javob bermayapti")
        response.status_code = 503
        return {"status": "unavailable", "database": "down"}
    return {"status": "ok", "database": "ok", "redis": "ok" if metrics.queue_length() is not None else "down"}


@router.get("/metrics", tags=["Ops"], summary="Operatsion ko'rsatkichlar (Prometheus)", response_class=Response,
            description="`METRICS_TOKEN` berilmagan bo'lsa o'chiq (404). Aks holda `Authorization: Bearer <METRICS_TOKEN>`. Faqat sonlar: Celery navbat uzunligi, xabarlar holati.")
def get_metrics(authorization: str = Header(""), db: Session = Depends(get_db)):
    if not settings.metrics_token:
        raise HTTPException(404, "Not Found")
    if not hmac.compare_digest(authorization, f"Bearer {settings.metrics_token}"):
        raise HTTPException(401, "Token noto'g'ri")
    return Response(metrics.render(db), media_type="text/plain; version=0.0.4")
