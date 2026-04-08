from celery import Celery
from core.config import get_settings

cfg = get_settings()

celery_app = Celery(
    "nl-lib",
    broker=cfg.REDIS_URL,
    backend=cfg.REDIS_URL,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    task_routes={
        "tasks.load_catalog_csv":    {"queue": "ingestion"},
        "tasks.process_single_book": {"queue": "ingestion"},
        "tasks.ingest_books_batch":  {"queue": "ingestion"},
    },
)
