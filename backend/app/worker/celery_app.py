"""Celery ilovasi (worker + beat). Broker/natija: Redis. Vazifalar `app.worker.tasks` da; jadval shu yerda."""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("clinic", broker=settings.redis_url, backend=settings.redis_url, include=["app.worker.tasks"])
celery_app.conf.update(
    timezone="UTC", enable_utc=True, task_acks_late=True, worker_prefetch_multiplier=1, task_time_limit=120,
    result_expires=3600, broker_connection_retry_on_startup=True,
    beat_schedule={
        "dispatch-messages": {"task": "app.worker.tasks.dispatch_messages", "schedule": 60.0},  # har daqiqa: navbatdagi xabarlar
        "schedule-reminders": {"task": "app.worker.tasks.schedule_reminders", "schedule": 300.0},  # har 5 daqiqa
        "warehouse-daily-scan": {"task": "app.worker.tasks.warehouse_daily_scan", "schedule": crontab(hour=2, minute=0)},  # 07:00 Toshkent
        "schedule-recalls": {"task": "app.worker.tasks.schedule_recalls", "schedule": 3600.0},  # har soat: qayta tashrif
    },
)
