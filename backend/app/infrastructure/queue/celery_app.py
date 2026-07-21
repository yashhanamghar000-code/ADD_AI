from celery import Celery

from app.config.settings import settings


def _normalize_redis_url(raw_url: str) -> str:
    if raw_url.startswith("rediss://") and "ssl_cert_reqs" not in raw_url:
        separator = "&" if "?" in raw_url else "?"
        return f"{raw_url}{separator}ssl_cert_reqs=CERT_NONE"
    return raw_url


_redis_url = _normalize_redis_url(settings.redis_url)

celery_app = Celery(
    "audito_worker",
    broker=_redis_url,
    backend=_redis_url,
    include=["app.infrastructure.queue.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    task_track_started=True,
    broker_transport_options={"visibility_timeout": 3600},
)
