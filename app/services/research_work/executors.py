"""executors.py — 생성 종류(kind) → 실행기. 디스패처가 여기서 고른다.

06a 는 핵심 개념, 06b 는 주제 카드·목차·절·문단을 더한다(06c 가 자식 카드·특징 추출).
실행기가 없는 kind 의 생성은 디스패처가 failed 로 닫는다.
"""
from services.research_work import concepts, outline, section, topic_card
from services.research_work.generate import Executor

EXECUTORS: dict[str, Executor] = {
    "concepts": concepts.EXECUTOR,
    "topic_card": topic_card.EXECUTOR,
    "outline": outline.EXECUTOR,
    "section": section.EXECUTOR,
}
