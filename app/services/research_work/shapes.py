"""shapes.py — 연구 어시스턴트 06b 의 상수·키 (spec §5-2~§5-6, 06b 계획 공통 계약 §1)

LLM·DB·무거운 import 가 없는 상수 모듈이다. 생성 실행기·API·조회 모양이 같은 값을 쓰도록 여기서만
정하고 다른 모듈은 가져다 쓴다(값을 다시 적지 않는다). JSONB 칼럼 안의 모양은 models/research_work.py
머리 주석에 있다.
"""

TOPIC_SEED_SLOTS = 4            # 이어가기 때 보고서 씨앗 카드 수(06b — 4번째도 보고서 씨앗, D8)
OTHER_DIRECTION_CARDS = 2       # [다른 방향] 한 번에 더 받는 카드 수
TOPIC_PAPERS_MAX = 6            # 카드 한 장에 주는 근거 후보 논문 수
MIN_TOPIC_EVIDENCE = 2          # 카드 내용 검사 — 근거 칩 최소 수(정함 4)
TOPIC_TITLE_MAX = 120           # 카드 제목 글자 상한(사용자 입력·모델 출력 공통)
TOPIC_QUESTION_MAX = 300        # 카드 연구 질문 글자 상한
MIN_READING_FOR_OUTLINE = 5     # 담음 5편 이상이면 [목차 만들기]
PAPERS_PER_GROUP = 4            # 담은 논문 4편당 선행연구 묶음 1개
MAX_GROUPS = 4
SECTION_PAPERS_MAX = 6          # 절 생성 입력 논문 상한
EXCERPT_CHARS = 1200            # 원문 대목 글자 상한(말줄임 없이 자른다)
ABSTRACT_CHARS = 600            # 절 입력의 초록 글자 상한(06b 는 특징 자리를 초록으로)
PATH_CHUNK_CHARS = 300          # 들어온 경로 팝오버의 대목 글자 상한
MAX_SECTION_PARAGRAPHS = 4      # 절 생성 결과 문단 상한(넘치면 앞에서 4개)
MAX_PARAGRAPH_CHARS = 3000      # 문단 하나 글자 상한(PUT 검증)
MAX_PARAGRAPHS_PUT = 12         # PUT 한 번의 문단 수 상한
READING_NOTE_MAX = 1000
GROUP_LABEL_MAX = 60
OUTLINE_QUESTION_MAX = 300
OUTLINE_METHOD_MAX = 1000
PROPOSAL_SECTIONS = ("topic", "background", "prior", "gap", "question", "method")   # 고정 6절(순서 = 문서 순서)
PRIOR_KEYS = ("prior.g1", "prior.g2", "prior.g3", "prior.g4")
GAP_KEY = "gap"
WRITABLE_SECTION_KEYS = PRIOR_KEYS + (GAP_KEY,)   # 06b 가 생성하는 절 키
PARA_STATES = ("proposed", "accepted", "edited", "authored")
EXPORTED_PARA_STATES = ("accepted", "edited", "authored")
OUTLINE_STATES = ("draft", "approved")
PHASE_ORDER = ("topics", "reading", "proposal", "done")   # models.WORK_PHASES 와 같은 순서 — 앞으로만 간다
GAP_NOTE = "소장 코퍼스에서 확인하지 않은 공백 후보"
OUTLINE_TARGET = "outline"      # kind=outline 생성의 target(연구마다 하나)
