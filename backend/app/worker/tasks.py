"""Celery vazifalari: yupqa o'ramlar (mantiq `services/` da, testlarda to'g'ridan-to'g'ri chaqiriladi)."""
from app.db.session import SessionLocal
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.dispatch_messages")
def dispatch_messages() -> dict:
    from app.services import messaging

    with SessionLocal() as db:
        return messaging.dispatch_due(db)


@celery_app.task(name="app.worker.tasks.schedule_reminders")
def schedule_reminders() -> dict:
    from app.services import reminders

    with SessionLocal() as db:
        return reminders.schedule_reminders(db)


@celery_app.task(name="app.worker.tasks.schedule_recalls")
def schedule_recalls() -> dict:
    from app.services import recalls

    with SessionLocal() as db:
        return recalls.schedule_recalls(db)
