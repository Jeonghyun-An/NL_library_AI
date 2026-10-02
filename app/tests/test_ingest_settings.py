"""적재 설정 — config 기본값과 docker-compose.yml 선언·워커 큐.

Portainer 는 compose 에 `${이름:-기본값}` 선언이 없는 스택 env 를 무시한다. 그래서 새 설정은
config 와 x-common-env 양쪽에 같은 기본값으로 있어야 한다.
"""
import re
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# 공통 계약의 설정 키 — 이름·타입·기본값
ROUND07_DEFAULTS = {
    "VLM_PAGE_CONCURRENCY": 2,
    "INGEST_EXTRACT_DEADLINE": 2700,
    "INGEST_STAGE_TIMEOUT_EXTRACT": 3600,
    "INGEST_RETRY_BACKOFF_SECONDS": "120,600",
    "LLM_RETRY_ATTEMPTS": 3,
    "LLM_RETRY_BACKOFF_SECONDS": "2,8",
    "SCAN_REPEAT_LINE_RATIO": 0.6,
    "SCAN_SHORT_PAGE_RATIO": 0.5,
    "SCAN_MIN_PAGES": 3,
    "ODL_TIMEOUT_BASE_SECONDS": 10.0,
    "ODL_TIMEOUT_PER_PAGE_SECONDS": 1.5,
    "ODL_IMAGE_OUTPUT": "off",
}


def _fresh_settings(monkeypatch):
    from core.config import Settings

    for key in ROUND07_DEFAULTS:
        monkeypatch.delenv(key, raising=False)
    return Settings(_env_file=None)


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _queues(command) -> set[str]:
    """compose command 가 celery 워커로 받는 큐 — 문자열·리스트(sh -c "…" 포함) 명령,
    -Q a,b · -Qa,b · --queues a,b · --queues=a,b."""
    if isinstance(command, str):
        args = command.split()
    elif isinstance(command, list):
        args = [token for part in command for token in str(part).split()]
    else:
        return set()
    names: list[str] = []
    for i, arg in enumerate(args):
        if arg in ("-Q", "--queues"):
            names += args[i + 1].split(",") if i + 1 < len(args) else []
        elif arg.startswith("--queues="):
            names += arg.split("=", 1)[1].split(",")
        elif arg.startswith("-Q"):
            names += arg[2:].split(",")
    return {name for name in names if name}


def test_round07_settings_have_contract_defaults(monkeypatch):
    s = _fresh_settings(monkeypatch)
    for key, expected in ROUND07_DEFAULTS.items():
        value = getattr(s, key)
        assert value == expected and type(value) is type(expected), f"{key}={value!r}"


def test_odl_image_output_accepts_only_cli_values(monkeypatch):
    # opendataloader-pdf CLI 가 받지 않는 값이면 java 가 문서마다 exit 2 로 끝나 모든 문서가 조용히 fitz 텍스트가
    # 된다 — 설정을 읽을 때 막는다
    from pydantic import ValidationError

    from core.config import Settings

    for value in ("off", "embedded", "external"):
        monkeypatch.setenv("ODL_IMAGE_OUTPUT", value)
        assert Settings(_env_file=None).ODL_IMAGE_OUTPUT == value
    for value in ("bogus", "OFF", ""):
        monkeypatch.setenv("ODL_IMAGE_OUTPUT", value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


def test_extract_deadline_ends_before_stale_timeout(monkeypatch):
    # 추출은 데드라인에서 스스로 멈추고 결과를 남긴다 — stale 판정이 그보다 먼저 오면 안 된다
    s = _fresh_settings(monkeypatch)
    assert s.INGEST_EXTRACT_DEADLINE < s.INGEST_STAGE_TIMEOUT_EXTRACT


def test_common_env_declares_round07_keys_with_config_defaults():
    env = _compose()["x-common-env"]
    for key, default in ROUND07_DEFAULTS.items():
        value = str(env.get(key))
        m = re.fullmatch(r"\$\{" + key + r":-(.*)\}", value)
        assert m, f"{key}: x-common-env 에 ${{{key}:-기본값}} 으로 선언해야 한다 (지금 {value!r})"
        assert type(default)(m.group(1)) == default, f"{key}: compose 기본값 {m.group(1)!r}"


def test_control_worker_takes_q_control_without_gpu():
    services = _compose()["services"]
    ctl = services["celery-control"]
    cpu = services["celery-cpu"]
    assert ctl["container_name"] == "nl-lib-celery-control"
    assert ctl["image"] == cpu["image"]
    assert ctl["networks"] == cpu["networks"]
    assert ctl["command"] == "celery -A workers.celery_app worker --loglevel=info --concurrency=1 -Q q_control"
    assert "deploy" not in ctl  # GPU 예약 없음
    # 정리 태스크(cleanup_temp_files)가 /app/data/downloads 를 지운다 — 데이터 볼륨만 단다
    assert ctl["volumes"] == ["/data/nl-lib/data:/app/data:rw"]
    assert ctl["environment"]["PYTHONPATH"] == "/app"
    assert ctl["environment"]["DB_HOST"] == "postgres"  # x-common-env 를 물고 있다
    # 다른 celery 워커와 같다 — 죽은 채 남으면 디스패치·stale 복구·정리가 모두 멈춘다
    assert ctl["restart"] == cpu["restart"] == "unless-stopped"


def test_services_running_odl_reap_orphans_with_init():
    # ODL 을 돌리는 서비스 — 추출(celery-cpu), 단건 흐름(celery-worker), 관리·도서 API(fastapi). 시간을 넘긴 ODL 의
    # java 손자는 고아가 돼 PID 1 로 넘어간다 — init(tini)이 PID 1 이어야 좀비로 남지 않는다
    services = _compose()["services"]
    for name in ("fastapi", "celery-worker", "celery-cpu"):
        assert services[name].get("init") is True, name


def test_no_page_image_area_setting():
    # 쪽 단위 이미지 면적 규칙은 두지 않는다 — 디지털 논문의 이미지 표지·간지를 다시 VLM 으로 보낸다.
    # 스캔본 판정은 문서 단위(SCAN_*)뿐이다
    from core.config import Settings

    assert "SCAN_IMAGE_AREA_RATIO" not in Settings.model_fields
    assert not hasattr(Settings, "SCAN_IMAGE_AREA_RATIO")
    assert "SCAN_IMAGE_AREA_RATIO" not in _compose()["x-common-env"]


def test_q_control_has_a_single_consumer():
    services = _compose()["services"]
    consumers = [name for name, svc in services.items() if "q_control" in _queues(svc.get("command"))]
    assert consumers == ["celery-control"]
    assert _queues(services["celery-cpu"]["command"]) == {"q_cpu"}


@pytest.mark.parametrize("command, expected", [
    ("celery -A workers.celery_app worker -Q q_cpu,q_control", {"q_cpu", "q_control"}),
    (["celery", "-A", "workers.celery_app", "worker", "-Q", "q_control"], {"q_control"}),
    ("celery -A workers.celery_app worker --queues=q_llm,q_control", {"q_llm", "q_control"}),
    ("celery -A workers.celery_app worker --queues q_control", {"q_control"}),
    (["celery", "worker", "--queues=q_control"], {"q_control"}),
    (["sh", "-c", "celery -A workers.celery_app worker -Q q_control"], {"q_control"}),
    ("celery -A workers.celery_app worker -Qq_control", {"q_control"}),
    ("celery -A workers.celery_app beat --loglevel=info", set()),
    (["milvus", "run", "standalone"], set()),
    (None, set()),
])
def test_queues_reads_every_command_form(command, expected):
    # 다른 서비스가 q_control 을 문자열·리스트 명령이나 긴 옵션으로 받아도 위 단일 소비자 검사가 잡는다
    assert _queues(command) == expected
