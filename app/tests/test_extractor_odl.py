"""extract_text_opendataloader — 쪽수 비례 타임아웃 → fitz 재저장본 재시도 → fitz 텍스트 폴백, 이미지 끄기.

ODL 변환(_odl_convert)은 목으로 바꾸고 산출물(markdown·json)을 직접 써 넣는다. 자식 프로세스를
끄는 동작만 실제 하위 프로세스로 확인한다.
"""
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import types
from pathlib import Path

import fitz
import pytest

from services.ingestion import extractor

SEP = "\n<<<ODL_PAGE_BREAK_%page-number%>>>\n"


@pytest.fixture(autouse=True)
def _odl_package(monkeypatch):
    """설치 확인용 import 만 통과시킨다 — 변환은 _odl_convert 목이 하므로 패키지가 없어도 된다."""
    monkeypatch.setitem(sys.modules, "opendataloader_pdf", types.ModuleType("opendataloader_pdf"))


def _pdf(texts: list[str]) -> bytes:
    doc = fitz.open()
    for text in texts:
        page = doc.new_page(width=300, height=400)
        if text:
            page.insert_text((36, 60), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def _write_outputs(out_dir: str, pages: dict[int, str], json_kids: list[dict] | None = None) -> None:
    md = "".join(SEP.replace("%page-number%", str(n)) + text for n, text in sorted(pages.items()))
    Path(out_dir, "doc.md").write_text(md, encoding="utf-8")
    Path(out_dir, "doc.json").write_text(json.dumps({"kids": json_kids or []}), encoding="utf-8")


def _patch_convert(monkeypatch, behaviours: list) -> list[dict]:
    """behaviours[i] — i 번째 변환에서 던질 예외, 또는 써 넣을 {쪽: 텍스트} / ({쪽: 텍스트}, json kids)."""
    calls: list[dict] = []

    async def fake_convert(kwargs, timeout):
        calls.append({**kwargs, "timeout": timeout, "input_exists": os.path.exists(kwargs["input_path"])})
        b = behaviours[len(calls) - 1]
        if isinstance(b, BaseException):
            raise b
        pages, kids = b if isinstance(b, tuple) else (b, None)
        _write_outputs(kwargs["output_dir"], pages, kids)

    monkeypatch.setattr(extractor, "_odl_convert", fake_convert)
    return calls


def _run(pdf: bytes, **kwargs):
    return asyncio.run(extractor.extract_text_opendataloader(None, "T_ODL", file_bytes=pdf, **kwargs))


def test_convert_writes_markdown_and_json_with_page_scaled_timeout(monkeypatch):
    calls = _patch_convert(monkeypatch, [{1: "첫 쪽 본문", 2: "둘째 쪽 본문"}])
    result = _run(_pdf(["a"] * 30))
    assert calls[0]["format"] == ["markdown", "json"]
    assert calls[0]["timeout"] == 15.0  # max(5, 30 × 0.5)
    assert [(p.page_num, p.text, p.method) for p in result.pages] == [
        (0, "첫 쪽 본문", "opendataloader"), (1, "둘째 쪽 본문", "opendataloader")]
    assert result.errors == []


def test_short_document_gets_base_timeout(monkeypatch):
    calls = _patch_convert(monkeypatch, [{1: "본문"}])
    _run(_pdf(["a"] * 4))
    assert calls[0]["timeout"] == 5.0


def test_timeout_retries_once_with_fitz_resaved_pdf(monkeypatch):
    calls = _patch_convert(monkeypatch, [TimeoutError(), {1: "재저장본 본문"}])
    result = _run(_pdf(["a", "b"]))
    assert len(calls) == 2
    assert calls[1]["input_path"] != calls[0]["input_path"]
    assert calls[1]["input_exists"]
    assert not os.path.exists(calls[1]["input_path"])  # 재저장 임시 파일은 지운다
    assert [p.text for p in result.pages] == ["재저장본 본문"]
    assert any("ODL 실패(원본)" in e for e in result.errors)


def test_value_error_on_the_original_also_retries_with_resaved_pdf(monkeypatch):
    """원본 변환의 ValueError(자식 실행 인자의 NUL 문자 등)도 재저장본 재시도·fitz 폴백으로 간다 — 재저장 갈래와
    같은 예외를 받는다. 바깥 except 로 새면 폴백 없이 빈 결과가 된다."""
    calls = _patch_convert(monkeypatch, [ValueError("embedded null byte"), {1: "재저장본 본문"}])
    result = _run(_pdf(["a", "b"]))
    assert len(calls) == 2
    assert [p.text for p in result.pages] == ["재저장본 본문"]
    assert any("ODL 실패(원본): embedded null byte" in e for e in result.errors)


def test_both_attempts_fail_falls_back_to_fitz_text(monkeypatch):
    _patch_convert(monkeypatch, [RuntimeError("ODL 변환 실패(exit 1)"), TimeoutError()])
    result = _run(_pdf(["First page body", "", "Third page body"]))
    assert [(p.page_num, p.text, p.method) for p in result.pages] == [
        (0, "First page body", "fitz"), (2, "Third page body", "fitz")]
    assert "ODL 실패 — fitz 텍스트로 대체" in result.errors


def test_unopenable_file_gets_no_resave_or_fitz_fallback(monkeypatch):
    calls = _patch_convert(monkeypatch, [RuntimeError("ODL 변환 실패(exit 1)")])
    result = _run(bytes(range(256)) * 40)
    assert len(calls) == 1
    assert calls[0]["timeout"] == 5.0
    assert result.pages == []
    assert any("ODL 실패(원본)" in e for e in result.errors)


def test_resave_error_of_any_type_still_falls_back_to_fitz_text(monkeypatch):
    """손상 PDF 의 fitz 재저장은 mupdf FzErrorBase 로 실패한다(PyMuPDF 1.24·1.28 — RuntimeError·ValueError·
    OSError 가 아니다). 그래도 fitz 텍스트 폴백으로 간다."""
    calls = _patch_convert(monkeypatch, [RuntimeError("ODL 변환 실패(exit 1)")])
    pdf = _pdf(["First page body"])  # tobytes 도 save 를 부르므로 save 를 바꾸기 전에 만든다

    def broken_save(self, *args, **kwargs):
        raise fitz.mupdf.FzErrorArgument("not a dict (null)")

    monkeypatch.setattr(fitz.Document, "save", broken_save)
    result = _run(pdf)
    assert len(calls) == 1
    assert [(p.page_num, p.text, p.method) for p in result.pages] == [(0, "First page body", "fitz")]
    assert any("ODL 실패(fitz 재저장본)" in e for e in result.errors)


def test_fitz_fallback_skips_only_the_page_whose_text_fails(monkeypatch):
    """폴백에서 쪽 하나의 get_text 실패('too many nested graphics states' 등)가 다른 쪽 텍스트까지 버리지 않는다 —
    그 쪽만 빠져 extract_text 가 'ODL 누락'으로 OCR 한다."""
    _patch_convert(monkeypatch, [TimeoutError(), TimeoutError()])
    real_get_text = fitz.Page.get_text

    def flaky_get_text(self, *args, **kwargs):
        if self.number == 1:
            raise RuntimeError("too many nested graphics states")
        return real_get_text(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_text", flaky_get_text)
    result = _run(_pdf(["First page body", "Second page body", "Third page body"]))
    assert [(p.page_num, p.method) for p in result.pages] == [(0, "fitz"), (2, "fitz")]
    assert "ODL 실패 — fitz 텍스트로 대체" in result.errors


# ── 폴백·변환 시간 기록 — 아이템 meta 에서 어느 문서가 ODL 폴백을 탔는지 센다 ─────────────


@pytest.fixture
def odl_clock(monkeypatch):
    """extractor 의 시계를 가짜로 바꾼다 — 변환 대역이 쓴 시간만큼만 흘러 odl_seconds 를 정확히 본다.
    쪽수 비례 상한은 기본값에 기대지 않게 5 + 쪽당 0.5 초로 둔다."""
    clock = types.SimpleNamespace(now=100.0)
    monkeypatch.setattr(extractor, "time", types.SimpleNamespace(monotonic=lambda: clock.now))
    monkeypatch.setattr(extractor.cfg, "ODL_TIMEOUT_BASE_SECONDS", 5.0)
    monkeypatch.setattr(extractor.cfg, "ODL_TIMEOUT_PER_PAGE_SECONDS", 0.5)
    return clock


def _patch_timed_convert(monkeypatch, clock, steps: list[tuple[float, object]]) -> list[dict]:
    """steps[i] = (걸린 초, _patch_convert 의 behaviour) — 가짜 시계를 그만큼 흘린 뒤 behaviour 대로 한다."""
    calls = _patch_convert(monkeypatch, [behaviour for _, behaviour in steps])
    convert = extractor._odl_convert

    async def timed_convert(kwargs, timeout):
        clock.now += steps[len(calls)][0]
        await convert(kwargs, timeout)

    monkeypatch.setattr(extractor, "_odl_convert", timed_convert)
    return calls


def _odl_time_logs(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records
            if r.levelno == logging.INFO and "초 / 상한 " in r.getMessage()]


@pytest.mark.parametrize("steps, fallback, method", [
    ([(12.5, {1: "본문"})], None, "opendataloader"),
    ([(15.0, TimeoutError()), (3.0, {1: "재저장본 본문"})], "resaved", "opendataloader"),
    ([(4.0, RuntimeError("ODL 변환 실패(exit 1)")), (15.0, TimeoutError())], "fitz", "fitz"),
], ids=["original", "resaved", "fitz"])
def test_odl_fallback_and_time_are_recorded(monkeypatch, odl_clock, caplog, steps, fallback, method):
    _patch_timed_convert(monkeypatch, odl_clock, steps)
    caplog.set_level(logging.INFO, logger=extractor.log.name)

    result = _run(_pdf(["First page body"] * 30))         # 상한 max(5, 30 × 0.5) = 15초

    assert result.odl_fallback == fallback
    assert result.odl_seconds == sum(seconds for seconds, _ in steps)
    assert {p.method for p in result.pages} == {method}
    # 변환 시도마다 한 줄 — 실패한 시도도 남긴다
    assert _odl_time_logs(caplog) == [f"[T_ODL] ODL {seconds:.1f}초 / 상한 15초" for seconds, _ in steps]


def test_failed_resave_still_reports_fitz_fallback(monkeypatch, odl_clock):
    _patch_timed_convert(monkeypatch, odl_clock, [(2.0, RuntimeError("ODL 변환 실패(exit 1)"))])
    pdf = _pdf(["First page body"])  # tobytes 도 save 를 부르므로 save 를 바꾸기 전에 만든다

    def broken_save(self, *args, **kwargs):
        raise fitz.mupdf.FzErrorArgument("not a dict (null)")

    monkeypatch.setattr(fitz.Document, "save", broken_save)
    result = _run(pdf)

    assert (result.odl_fallback, result.odl_seconds) == ("fitz", 2.0)


def test_unopenable_file_has_no_fallback_but_records_time(monkeypatch, odl_clock, caplog):
    """fitz 로도 안 열리는 파일은 재저장·fitz 폴백이 없다 — 폴백 None, 시도 한 번의 시간만 남는다."""
    _patch_timed_convert(monkeypatch, odl_clock, [(1.5, RuntimeError("ODL 변환 실패(exit 1)"))])
    caplog.set_level(logging.INFO, logger=extractor.log.name)

    result = _run(bytes(range(256)) * 40)

    assert (result.pages, result.odl_fallback, result.odl_seconds) == ([], None, 1.5)
    assert _odl_time_logs(caplog) == ["[T_ODL] ODL 1.5초 / 상한 5초"]


@pytest.mark.parametrize("pdf", [_pdf(["First page body has enough letters to keep."] * 2), bytes(range(256)) * 40],
                         ids=["normal", "fitz_cannot_open"])
def test_extract_text_carries_odl_fallback_and_time(monkeypatch, pdf):
    """extract_text 는 1티어 결과의 폴백·변환 시간을 그대로 싣는다 — fitz 로 안 열려 ODL 결과만 돌려줄 때도."""
    async def fake_odl(file_path, book_id, *, file_bytes=None, max_pages=None):
        res = extractor.ExtractionResult(book_id=book_id, total_pages=2)
        res.pages = [extractor.PageResult(n, "First page body has enough letters to keep.", "fitz", 0.5)
                     for n in range(2)]
        res.odl_fallback, res.odl_seconds = "fitz", 31.25
        return res

    monkeypatch.setattr(extractor, "extract_text_opendataloader", fake_odl)

    result = asyncio.run(extractor.extract_text(None, "T_ODL", file_bytes=pdf))

    assert (result.odl_fallback, result.odl_seconds) == ("fitz", 31.25)
    assert len(result.pages) == 2


def test_nonzero_exit_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(extractor, "_ODL_CHILD", "import sys; sys.stderr.write('boom'); sys.exit(3)")
    with pytest.raises(RuntimeError, match="exit 3"):
        asyncio.run(extractor._odl_convert({}, 30))


def test_failure_message_keeps_the_cause_and_the_last_line(monkeypatch):
    """opendataloader 의 run_jar 는 실패하면 java 출력(Output:·Stderr:·Stdout: 구획)을 먼저 찍고 끝에
    CalledProcessError 추적(맨 끝 줄에 CLI 인자 전부)을 찍는다 — 끝 300자만 남기면 원인 줄이 잘린다."""
    script = r'''
import sys
w = sys.stderr.write
w("Error running opendataloader-pdf CLI.\nReturn code: 2\n")
w("Stdout: " + "".join("INFO processing element %d of the document tree\n" % i for i in range(200)))
w("SEVERE: Unsupported image output mode 'bogus'\n")
w("".join("INFO cleanup step %d\n" % i for i in range(200)))
w('Traceback (most recent call last):\n  File "<string>", line 3, in <module>\n')
args = ", ".join("'--option-%d'" % i for i in range(80))
w("subprocess.CalledProcessError: Command '['java', '-jar', 'opendataloader-pdf-cli.jar', " + args
  + "]' returned non-zero exit status 2.\n")
sys.exit(1)
'''
    monkeypatch.setattr(extractor, "_ODL_CHILD", script)

    with pytest.raises(RuntimeError) as exc:
        asyncio.run(extractor._odl_convert({}, 30))

    message = str(exc.value)
    assert message.startswith("ODL 변환 실패(exit 1): ")
    assert "Unsupported image output mode 'bogus'" in message
    assert message.endswith("returned non-zero exit status 2.")
    assert "INFO" not in message and len(message) <= 650


def _sleeping_grandchild_script(pid_file: Path) -> str:
    """잠자는 손자(java 자리)를 띄워 pid 를 남기고 자기도 잠드는 자식 — pid 는 다 쓴 뒤 이름을 바꿔 반쯤 쓴 파일이 없다."""
    tmp = str(pid_file) + ".tmp"
    return (
        "import os, subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        f"open({tmp!r}, 'w').write(str(p.pid))\n"
        f"os.replace({tmp!r}, {str(pid_file)!r})\n"
        "time.sleep(20)\n"
    )


def _wait_for_pid_file(pid_file: Path, seconds: float = 5.0) -> int:
    for _ in range(int(seconds / 0.05)):
        if pid_file.exists():
            return int(pid_file.read_text())
        time.sleep(0.05)
    pytest.fail(f"{seconds:g}초 안에 손자 pid 를 받지 못했다")


def _gone(pid: int) -> bool:
    """프로세스가 끝났는가 — 없거나, 회수 전 좀비(Z)이거나, 확인하는 사이 /proc 에서 사라졌다(리눅스)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return True


def test_timeout_kills_child_process_group(monkeypatch, tmp_path):
    """시간을 넘기면 자식(파이썬)과 그 자식(java 자리)을 함께 끈다. 손자 확인은 killpg 가 있는 리눅스에서만."""
    pid_file = tmp_path / "grandchild.pid"
    monkeypatch.setattr(extractor, "_ODL_CHILD", _sleeping_grandchild_script(pid_file))
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(extractor._odl_convert({}, 3.0))
    assert time.monotonic() - t0 < 10
    if sys.platform == "win32":
        return
    grandchild = _wait_for_pid_file(pid_file)
    for _ in range(50):
        if _gone(grandchild):
            break
        time.sleep(0.1)
    else:
        pytest.fail("timeout 뒤에도 손자 프로세스가 살아 있다")


def test_child_gets_the_timeout_as_its_second_argument(monkeypatch, tmp_path):
    seen = tmp_path / "argv.json"
    monkeypatch.setattr(extractor, "_ODL_CHILD", f"import json, sys; open({str(seen)!r}, 'w').write(json.dumps(sys.argv[1:]))")
    asyncio.run(extractor._odl_convert({"input_path": "x.pdf"}, 12.5))
    assert json.loads(seen.read_text()) == [json.dumps({"input_path": "x.pdf"}), "12.5"]


@pytest.mark.skipif(not hasattr(signal, "alarm"), reason="signal.alarm·killpg 가 없다(Windows 개발 PC)")
def test_child_kills_its_own_group_when_nobody_else_does(tmp_path):
    """부모(Celery 풀 자식)가 죽으면(revoke(terminate=True) 등) 시간을 넘겨도 끌 사람이 없다 — ODL 자식은 스스로
    int(timeout) + 5 초 뒤 자기 프로세스 그룹을 끈다. 진짜 _ODL_CHILD 를 가짜 opendataloader_pdf(잠자는 손자를
    띄우고 잠든다)로 직접 돌려 자식과 손자가 모두 끝나는지 본다."""
    pid_file = tmp_path / "grandchild.pid"
    fake_pkg = tmp_path / "fake_odl"
    fake_pkg.mkdir()
    body = "\n".join("    " + line for line in _sleeping_grandchild_script(pid_file).splitlines())
    (fake_pkg / "opendataloader_pdf.py").write_text(f"def convert(**kwargs):\n{body}\n", encoding="utf-8")

    t0 = time.monotonic()
    child = subprocess.Popen(
        [sys.executable, "-c", extractor._ODL_CHILD, "{}", "1"],   # 부모가 하듯 새 세션 — killpg(0) 이 자기 그룹만 끈다
        env={**os.environ, "PYTHONPATH": str(fake_pkg)}, start_new_session=True,
    )
    try:
        grandchild = _wait_for_pid_file(pid_file)
        assert child.wait(timeout=20) == -signal.SIGKILL
        assert 5 <= time.monotonic() - t0 < 20                     # int(1) + 5 = 6초 뒤
        for _ in range(50):
            if _gone(grandchild):
                break
            time.sleep(0.1)
        else:
            pytest.fail("자식이 스스로 끝난 뒤에도 손자 프로세스가 살아 있다")
    finally:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGKILL)


# ── 이미지 끄기(ODL_IMAGE_OUTPUT) ──────────────────────────────────


@pytest.mark.parametrize("mode", ["off", "embedded"])
def test_convert_uses_image_output_setting(monkeypatch, mode):
    calls = _patch_convert(monkeypatch, [{1: "본문"}])
    monkeypatch.setattr(extractor.cfg, "ODL_IMAGE_OUTPUT", mode)
    _run(_pdf(["a"]))
    assert calls[0]["image_output"] == mode


def test_image_only_page_stays_as_empty_odl_page(monkeypatch):
    """image_output=off 면 그림만 있는 쪽이 markdown 에서 빠진다 — json 의 그림 요소로 빈 쪽을 남긴다."""
    kids = [{"type": "paragraph", "page number": 1, "content": "첫 쪽"},
            {"type": "image", "page number": 2},
            {"type": "paragraph", "page number": 3, "content": "셋째 쪽"}]
    _patch_convert(monkeypatch, [({1: "첫 쪽", 3: "셋째 쪽"}, kids)])
    result = _run(_pdf(["a", "b", "c"]))
    assert [(p.page_num, p.text) for p in result.pages] == [(0, "첫 쪽"), (1, ""), (2, "셋째 쪽")]
