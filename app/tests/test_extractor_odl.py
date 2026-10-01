"""extract_text_opendataloader — 쪽수 비례 타임아웃 → fitz 재저장본 재시도 → fitz 텍스트 폴백, 이미지 끄기.

ODL 변환(_odl_convert)은 목으로 바꾸고 산출물(markdown·json)을 직접 써 넣는다. 자식 프로세스를
끄는 동작만 실제 하위 프로세스로 확인한다.
"""
import asyncio
import json
import os
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


def test_nonzero_exit_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(extractor, "_ODL_CHILD", "import sys; sys.stderr.write('boom'); sys.exit(3)")
    with pytest.raises(RuntimeError, match="exit 3"):
        asyncio.run(extractor._odl_convert({}, 30))


def test_timeout_kills_child_process_group(monkeypatch, tmp_path):
    """시간을 넘기면 자식(파이썬)과 그 자식(java 자리)을 함께 끈다. 손자 확인은 killpg 가 있는 리눅스에서만."""
    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))\n"
        "time.sleep(20)\n"
    )
    monkeypatch.setattr(extractor, "_ODL_CHILD", script)
    t0 = time.monotonic()
    with pytest.raises(TimeoutError):
        asyncio.run(extractor._odl_convert({}, 2.0))
    assert time.monotonic() - t0 < 10
    if sys.platform == "win32":
        return
    grandchild = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        with open(f"/proc/{grandchild}/stat") as f:  # 회수 전 좀비(Z)면 끝난 것으로 본다
            if f.read().split()[2] == "Z":
                break
        time.sleep(0.1)
    else:
        pytest.fail("timeout 뒤에도 손자 프로세스가 살아 있다")


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
