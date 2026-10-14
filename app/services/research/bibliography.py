"""bibliography.py — 논문 끝 참고문헌 목록 조각인가 (순수 함수)

적재는 본문을 청킹할 때 참고문헌까지 그대로 쪽수 달린 청크로 만들고, 청크에는 절 종류 표시가 없다
(Milvus 필드·book_sections 어디에도 없다. 참고문헌은 보강 단계가 library_catalog.extra["references"] 에 따로 뽑을
뿐이다). 참고문헌 목록에는 주제어가 든 논문 제목이 빽빽해 리랭커 점수가 본문과 같거나 더 높게 나온다. 그 조각이
근거가 되면 인용칩이 서지 목록을 원문 대목으로 띄우고(겹치는 대목 문장을 찾지 못한다), 생성이 참고문헌 항목을 그
논문의 내용처럼 쓰며, 참고문헌 속 제목만 맞은 무관한 논문이 근거로 채택된다.

그래서 글자만 보고 가른다. 운영 근거 청크 869개(딥리서치 보고서 48개, 짧은 조각·초록 머리 갈래는 630e0d65 근거를 더한
881개)로 맞춘 규칙이고, 거기서 본문 오탐은 없었다.
본문으로 남기는 쪽으로 기운다 — 놓친 참고문헌은 지금과 같지만 잘못 거른 본문은 근거를 잃는다.
"""
import re

# 참고문헌 항목에 흔하고 본문 문장에는 드문 서지 꼴
_ENTRY_SHAPES = (
    re.compile(r"\bpp?\s*\.\s*\d"),                                                   # pp.402 · p. 12
    re.compile(r"\d{1,4}\s*\(\s*\d{1,3}(?:\s*[-,/·]\s*\d{1,3})?\s*\)\s*[,:.]"),        # 13(5), · 36(2):
    re.compile(r"\d{1,4}\s*(?:\(\s*\d{1,3}\s*\))?\s*:\s*\d{1,5}\s*[-–~∼～－]\s*\d{1,5}"),  # 23: 209-231 · 8(3) : 257-261
    re.compile(r"(?:19|20)\d{2}\s*;\s*\d+"),                                          # 1998;2:89 (밴쿠버)
    re.compile(r"제\s*\d+\s*(?:권|호|집)"),                                            # 제35권 제2호
    re.compile(r"\b(?:Vol|vol|VOL|No|no)\s*\.\s*\d"),                                  # Vol. 61
    re.compile(r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)\s*[.,:]"),                            # (2012). · (2000) :
    # , 2013. — 접수일 '접수 : 2010.' 과 날짜 '2006. 10. 4.' 는 서지의 연도가 아니다
    re.compile(r"(?<![\d.])(?<!:\s)(?<!:)(?:19|20)\d{2}[a-z]?\s*\.(?=\s|$)(?!\s*\d{1,2}\s*\.)"),
    re.compile(r"(?m)(?:^|\s)-?\s*\[\d{1,3}\]\s"),                                    # - [16] Norbeck
    re.compile(r"(?m)(?:^|\s-\s)\d{1,3}\)\s+[A-Z가-힣]"),                              # - 49) Camacho · 25) Lavretsky
    re.compile(r"[“\"「『󰡔][^”\"」』󰡕]{6,160}[”\"」』󰡕]\s*[,.]"),                        # “제목”, · 「제목」.
    re.compile(r"\b[A-Z][a-zA-Z'\-]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?\s*(?:,|&|and\b|\()"),  # Selig, J. P., &
    re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)?\s[A-Z]{1,3},"),                       # Bruce ML, Seeman TE,
)
# 본문 문장 — 한국어 서술 종결, 영어 서술 동사. 종결과 마침표 사이의 괄호 인용 '…하였다(김철수, 2012: 45-67).'·
# '…하였다[3].' 과 마침표 뒤에 바로 붙는 각주 번호 '…하였다.12)'·닫는 따옴표 '…하였다.”' 도 서술 종결로 센다
_KOREAN_SENTENCE_END = re.compile(
    r"(?:다|요|함|음|임)\s*(?:\([^()]{1,120}\)|\[[^\[\]]{1,30}\])?\s*[.。](?=\s|$|\[|[\"”’」』]|\d{1,3}\))")
_ENGLISH_PROSE = re.compile(
    r"\b(?:is|are|was|were|we|our|this study|these|has|have|had|will|can|could|may|should|showed|found|suggests?)\b",
    re.I)
# 참고문헌 머리 — 마크다운·꺾쇠(HTML 이스케이프 포함) 장식을 허용한다. 단수 'Reference' 는 'Reference service'(참고봉사)
# 같은 본문 낱말이라 머리로 보지 않는다
_HEAD_WORD = (r"(?:#{1,6}\s*)?(?:&lt;|<|\[|【)?\s*"
              r"(?:참\s*고\s*문\s*헌|References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*(?:&gt;|>|\]|】)?")
# 머리가 제 줄에 혼자 있거나 청크 맨 앞(쪽 머리글 60자 안)에 있을 때만 머리로 본다 — 목차의 '<참 고 문 헌>'·
# 본문의 '참고문헌 분석' 같은 낱말을 머리로 보지 않게. 청크 맨 앞의 머리는 그 줄이 끝나거나 서지 항목이 바로 이을 때만
# 머리다 — 뒤에 소문자 낱말('Bibliography instruction'·'References to')이나 띄어 쓴 한글 낱말 둘('참고문헌 분석에
# 관한')이 이으면 절 제목·본문 낱말이다. 항목 첫머리 '고병률.'·'김철수 (2010).'·'Kim, J.' 는 머리로 둔다
_HEAD_LINE = re.compile(r"(?m)^[ \t]*" + _HEAD_WORD + r"[ \t]*$")
_HEAD_START = re.compile(
    r"^.{0,60}?(?:^|\s)(" + _HEAD_WORD + r")"
    r"(?=[ \t]*(?:\r?\n|$)|[ \t]+(?![ \t])(?![a-z])(?![가-힣]+[ \t]+[가-힣]))", re.S)

_HEAD_TAIL_MIN = 0.6     # 머리 뒤 글이 청크에서 차지하는 몫
_ENTRIES_MIN = 4         # 머리가 없을 때 서지 꼴 개수
_ENTRIES_PER_K_MIN = 5   # 1000자당 서지 꼴
_ENTRIES_PER_PROSE = 5   # 서술 문장(한국어 종결 + 영어 서술 동사/3) 하나당 서지 꼴
_SHAPE_KINDS_MIN = 2     # 서로 다른 서지 꼴 종류

# 짧은 조각 — 쪽 경계에서 잘려 항목 두어 개만 남은 참고문헌은 머리도 없고 서지 꼴이 _ENTRIES_MIN 에 못 미친다. 서술이
# 하나도 없고 서지 꼴이 떨어진 두 자리 이상에 있을 때만 본다. _SPOT_GAP 안에 붙은 꼴은 한 자리다 — 학술지 첫 쪽 머리
# '2016, Vol. 32, No. 4, pp. 183～204.'·그림 출처 '자료: 정효채 등. (2013). p.74' 는 꼴 여럿이 한 항목에 몰려 있다
_SHORT_MAX = 300
_SPOT_GAP = 40
# 참고문헌 꼬리 + 다음 쪽 영문 제목·초록 — 한국어 논문 끝 영문 초록 쪽이 참고문헌 마지막 쪽과 한 청크가 된 것. 앞 400자만
# 생성에 들어가 초록 대신 서지가 요약된다. 제 줄에 혼자 있는 'Abstract' 앞이 서술 없는 서지이고, 첫 제목 줄('#') 앞에
# 저자-연도 '(1996).' 가 있을 때만 본다 — 학술지 첫 쪽 머리의 'No. 3 (2017).' 는 저자 이니셜 뒤가 아니고, 첫 쪽 인용 안내
# 'Hong, G. D. (2017).' 는 논문 제목 뒤에 있다
_ABSTRACT_LINE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:&lt;|<|\[)?[ \t]*(?:Abstract|ABSTRACT)[ \t]*(?:&gt;|>|\])?[ \t]*$")
_AUTHOR_YEAR = re.compile(r"(?:\A|\b[A-Z]\.)\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)\s*[.,:]")
_HEADING_LINE = re.compile(r"(?m)^#{1,6}[ \t]")
_TAIL_BEFORE_ABSTRACT_MIN = 40


def _entry_spots(text: str) -> int:
    """서지 꼴이 놓인 자리 수 — _SPOT_GAP 안에 붙은 꼴은 한 자리로 센다."""
    spans = sorted(m.span() for shape in _ENTRY_SHAPES for m in shape.finditer(text))
    spots, end = 0, float("-inf")
    for start, stop in spans:
        if start - end > _SPOT_GAP:
            spots += 1
        end = max(end, stop)
    return spots


def _no_prose(text: str) -> bool:
    return not _KOREAN_SENTENCE_END.search(text) and not _ENGLISH_PROSE.search(text)


def _bibliography_before_abstract(text: str) -> bool:
    """제 줄의 'Abstract' 앞이 참고문헌 꼬리인가 — 서술 0·서지 꼴 두 종류 이상·첫 제목 줄 앞의 저자-연도."""
    abstract = _ABSTRACT_LINE.search(text)
    if not abstract or abstract.start() < _TAIL_BEFORE_ABSTRACT_MIN:
        return False
    before = text[:abstract.start()]
    heading = _HEADING_LINE.search(before)
    return (_AUTHOR_YEAR.search(before, 0, heading.start() if heading else len(before)) is not None
            and _no_prose(before)
            and sum(1 for shape in _ENTRY_SHAPES if shape.search(before)) >= _SHAPE_KINDS_MIN)


def looks_like_bibliography(text: str) -> bool:
    """참고문헌 목록 조각이면 True. 표 청크([표]로 시작)는 각주 서지가 섞여도 수치 근거라 늘 False."""
    if not text or text.startswith("[표]"):
        return False
    counts = [len(shape.findall(text)) for shape in _ENTRY_SHAPES]
    entries = sum(counts)
    # 서술 문장 수 — 한국어 종결 + 영어 서술 동사/3. 머리가 있어도 서술이 하나를 넘으면 머리 갈래로는 거르지 않는다
    prose = len(_KOREAN_SENTENCE_END.findall(text)) + len(_ENGLISH_PROSE.findall(text)) / 3

    head = _HEAD_LINE.search(text)
    head_at = head.start() if head else None
    if head_at is None and (head := _HEAD_START.search(text)):
        head_at = head.start(1)
    if head_at is not None:
        tail = (len(text) - head_at) / len(text)
        if tail >= _HEAD_TAIL_MIN and prose <= 1 and entries >= 2:
            return True

    kinds = sum(1 for c in counts if c)
    if len(text) <= _SHORT_MAX and kinds >= _SHAPE_KINDS_MIN and prose == 0 and _entry_spots(text) >= 2:
        return True
    if _bibliography_before_abstract(text):
        return True

    # 머리 없는 목록 — 같은 꼴 하나만 되풀이되는 글(번호 목록 '- 1)', 본문 번호 인용 ' [3] ', 법률 번호 '제8029호')은
    # 본문에도 있어 서로 다른 꼴이 둘 이상일 때만 목록으로 본다
    return (entries >= _ENTRIES_MIN
            and entries * 1000 / len(text) >= _ENTRIES_PER_K_MIN
            and entries >= _ENTRIES_PER_PROSE * prose
            and kinds >= _SHAPE_KINDS_MIN)
