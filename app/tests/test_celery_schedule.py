"""workers/celery_app.py — beat 일정의 expires 와 visibility_timeout.

celery 는 로컬 venv 에 없다. 더미 Celery 로 celery_app 을 새로 import 해 conf 만 본다
(test_research_tasks.py 와 같은 방식 — 함정 13번).
"""
import importlib
import re
import sys
import types
from pathlib import Path

import pytest
import yaml

COMPOSE = Path(__file__).resolve().parents[2] / "docker-compose.yml"

# 각 주기보다 짧게 — 늦게 받은 옛 틱은 버린다
EXPECTED_EXPIRES = {
    "dispatch-job-items": 25,
    "cleanup-temp-files": 3000,
    "reap-stale-research": 500,
}


class _FakeConf:
    def update(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


class _FakeCelery:
    def __init__(self, *a, **kw):
        self.conf = _FakeConf()

    def task(self, *a, **kw):
        def _decorator(fn):
            return fn
        return _decorator


@pytest.fixture
def conf(monkeypatch):
    celery_mod = types.ModuleType("celery")
    celery_mod.Celery = _FakeCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)
    # 앞 테스트가 다른 더미로 import 해 둔 celery_app 을 물려받지 않는다 — 끝나면 원래대로 되돌린다
    monkeypatch.setattr(importlib.import_module("workers"), "celery_app", None, raising=False)
    monkeypatch.setitem(sys.modules, "workers.celery_app", None)
    del sys.modules["workers.celery_app"]
    return importlib.import_module("workers.celery_app").celery_app.conf


def test_beat_ticks_expire_before_the_next_tick(conf):
    schedule = conf.beat_schedule
    assert set(schedule) == set(EXPECTED_EXPIRES)
    for name, entry in schedule.items():
        expires = entry["options"]["expires"]
        assert expires == EXPECTED_EXPIRES[name], name
        assert 0 < expires < entry["schedule"], name


def test_compose_extract_stale_timeout_is_inside_visibility_timeout(conf):
    # 실행 중인 추출 메시지는 visibility_timeout 이 지나면 재전달된다 — stale 판정이 그 안쪽이어야 한다
    env = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["x-common-env"]
    m = re.fullmatch(r"\$\{INGEST_STAGE_TIMEOUT_EXTRACT:-(\d+)\}", env["INGEST_STAGE_TIMEOUT_EXTRACT"])
    assert int(m.group(1)) < conf.broker_transport_options["visibility_timeout"]
