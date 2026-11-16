"""Ixtiyoriy Sentry (SENTRY_DSN). Shaxsiy ma'lumot yuborilmaydi: `send_default_pii=False`, so'rov tanasi va sarlavhalar o'chiriladi."""
import logging

from app.core.config import settings

log = logging.getLogger("app.observability")


def _scrub(event: dict, hint: dict) -> dict:
    req = event.get("request") or {}
    for key in ("data", "cookies", "headers", "query_string", "env"):
        req.pop(key, None)
    event.pop("user", None)
    return event


def init_sentry() -> bool:
    if not settings.sentry_dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        log.warning("SENTRY_DSN berilgan, lekin sentry-sdk o'rnatilmagan")
        return False
    sentry_sdk.init(dsn=settings.sentry_dsn, send_default_pii=False, max_request_body_size="never", before_send=_scrub,
                    traces_sample_rate=settings.sentry_traces_sample_rate, environment=settings.app_env)
    log.info("Sentry yoqildi")
    return True
