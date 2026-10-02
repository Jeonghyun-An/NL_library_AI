"""research_work — 연구 어시스턴트(round06): 이어간 연구의 생성(핵심 개념·주제 카드·계획서 …).

생성 1건 = research_generations 1행 = Celery 메시지 1개. 워커는 DB 텍스트 조회와 LLM 호출만 한다
(임베딩이 필요한 입력은 생성을 넣는 FastAPI 가 만든다 — spec §6-3).
"""
