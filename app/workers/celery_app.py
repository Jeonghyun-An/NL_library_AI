from celery import Celery
from core.config import get_settings

cfg = get_settings()

celery_app = Celery(
    "nl-lib",
    broker=cfg.REDIS_URL,
    backend=cfg.REDIS_URL,
    include=["workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    # 긴 태스크에 적합한 설정: 워커 사망 시 메시지 재전달, 선취 최소화
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"visibility_timeout": 7200},
    task_routes={
        "tasks.load_catalog_xlsx":     {"queue": "ingestion"},
        "tasks.load_kci_catalog_xlsx": {"queue": "ingestion"},
        "tasks.ingest_books_batch":    {"queue": "ingestion"},
    },
)
