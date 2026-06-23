"""_format_history_for_rewrite — 대화 질의 재구성용 히스토리 포맷 (순수 함수)."""
from services.chat import book_chat


def test_empty_history():
    assert book_chat._format_history_for_rewrite([], 6) == ""


def test_role_labels_and_join():
    history = [
        {"role": "user", "content": "이 책의 주제는?"},
        {"role": "assistant", "content": "생명의 소중함입니다."},
    ]
    out = book_chat._format_history_for_rewrite(history, 6)
    assert out == "사용자: 이 책의 주제는?\n도우미: 생명의 소중함입니다."


def test_truncates_to_last_n():
    history = [{"role": "user", "content": f"q{i}"} for i in range(10)]
    out = book_chat._format_history_for_rewrite(history, 3)
    lines = out.splitlines()
    assert len(lines) == 3
    assert lines[-1] == "사용자: q9"   # 가장 최근 메시지 포함
    assert "q6" not in out             # 오래된 메시지 제외


def test_skips_blank_content():
    history = [
        {"role": "user", "content": "  "},
        {"role": "assistant", "content": ""},
        {"role": "user", "content": "왜 그런가요?"},
    ]
    out = book_chat._format_history_for_rewrite(history, 6)
    assert out == "사용자: 왜 그런가요?"
