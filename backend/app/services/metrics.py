# ruff: noqa: E501
"""Operatsion ko'rsatkichlar (Prometheus matn formati): Celery navbat uzunligi, xabarlar holati. PII yo'q, faqat sonlar."""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Message
from app.schemas.enums import MessageStatus

log = logging.getLogger("app.metrics")
QUEUES = ("celery",)       # standart Celery navbati


def queue_length(queue: str = "celery") -> int | None:
    """Redis'dagi kutayotgan Celery vazifalari soni; Redis yetib bo'lmasa None."""
    try:
        import redis
        return int(redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).llen(queue))
    except Exception:
        log.warning("Redis navbat uzunligini o'qib bo'lmadi")
        return None


def render(db: Session) -> str:
    now = datetime.now(UTC)
    lines = ["# HELP clinic_celery_queue_length Redis'dagi kutayotgan Celery vazifalari", "# TYPE clinic_celery_queue_length gauge"]
    for q in QUEUES:
        n = queue_length(q)
        if n is not None:
            lines.append(f'clinic_celery_queue_length{{queue="{q}"}} {n}')
    lines += ["# HELP clinic_redis_up Redis ulanishi (1/0)", "# TYPE clinic_redis_up gauge", f"clinic_redis_up {int(queue_length() is not None)}"]
    counts = dict(db.execute(select(Message.status, func.count()).group_by(Message.status)).all())
    lines += ["# HELP clinic_messages_total Xabarlar holati bo'yicha", "# TYPE clinic_messages_total gauge"]
    for st in MessageStatus:
        lines.append(f'clinic_messages_total{{status="{st.value}"}} {counts.get(st, 0)}')
    overdue = db.scalar(select(func.count()).where(Message.status == MessageStatus.queued, Message.scheduled_at < now - timedelta(minutes=10)))
    lines += ["# HELP clinic_messages_overdue_queued Rejalashtirilgan vaqtdan 10 daqiqadan ortiq kechikkan navbatdagi xabarlar",
              "# TYPE clinic_messages_overdue_queued gauge", f"clinic_messages_overdue_queued {overdue or 0}"]
    return "\n".join(lines) + "\n"
