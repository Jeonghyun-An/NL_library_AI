from celery import Celery
from core.config import get_settings

cfg = get_settings()

celery_app = Celery(
    "nl-lib",
    broker=cfg.REDIS_URL,
    backend=cfg.REDIS_URL,
    include=["workers.tasks", "workers.research_tasks"],
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
        # 단건/메타 적재 흐름 (기존)
        "tasks.load_catalog_xlsx":     {"queue": "ingestion"},
        "tasks.load_kci_catalog_xlsx": {"queue": "ingestion"},
        "tasks.ingest_books_batch":    {"queue": "ingestion"},
        # 배치 잡 레이어 — CPU(추출) / LLM(요약·소개) / 임베딩 큐 분리
        "tasks.stage_extract":     {"queue": "q_cpu"},
        "tasks.stage_summarize":   {"queue": "q_llm"},
        "tasks.stage_embed_index": {"queue": "q_embed"},
        "tasks.stage_finalize":    {"queue": "q_llm"},
        "tasks.dispatch_job_items":  {"queue": "q_control"},
        "tasks.cleanup_temp_files":  {"queue": "q_control"},
        # 딥리서치 — 계획·실행은 설정 큐(core/config.py RESEARCH_QUEUE·RESEARCH_PLAN_QUEUE
        # 주석), stale 회수는 제어 큐. 적재 요약과 같은 q_llm FIFO 에 있으면 사용자의 계획
        # 요청이 요약 수십 건 뒤에 선다.
        "tasks.plan_deep_research":  {"queue": cfg.RESEARCH_PLAN_QUEUE},
        "tasks.run_deep_research":   {"queue": cfg.RESEARCH_QUEUE},
        "tasks.reap_stale_research": {"queue": "q_control"},
    },
    beat_schedule={
        "dispatch-job-items": {
            "task": "tasks.dispatch_job_items",
            "schedule": 30.0,
        },
        "cleanup-temp-files": {
            "task": "tasks.cleanup_temp_files",
            "schedule": 3600.0,
        },
        # 워커가 죽으면 잡이 running 인 채 영원히 남는다 — 하드 리밋을 넘긴 것만 회수한다
        # (research_tasks.STALE_MINUTES)
        "reap-stale-research": {
            "task": "tasks.reap_stale_research",
            "schedule": 600.0,
        },
    },
)
