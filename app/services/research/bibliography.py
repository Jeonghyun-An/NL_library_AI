"""bibliography.py — 논문 끝 참고문헌 목록 조각인가 (순수 함수)

적재는 본문을 청킹할 때 참고문헌까지 그대로 쪽수 달린 청크로 만들고, 청크에는 절 종류 표시가 없다
(Milvus 필드·book_sections 어디에도 없다. 참고문헌은 보강 단계가 library_catalog.extra["references"] 에 따로 뽑을
뿐이다). 참고문헌 목록에는 주제어가 든 논문 제목이 빽빽해 리랭커 점수가 본문과 같거나 더 높게 나온다. 그 조각이
근거가 되면 인용칩이 서지 목록을 원문 대목으로 띄우고(겹치는 대목 문장을 찾지 못한다), 생성이 참고문헌 항목을 그
논문의 내용처럼 쓰며, 참고문헌 속 제목만 맞은 무관한 논문이 근거로 채택된다.

그래서 글자만 보고 가른다. 운영 근거 청크 869개(딥리서치 보고서 48개, 짧은 조각·초록 머리 갈래는 630e0d65 근거를 더한
881개, 학위논문 꼴은 4차 배포 뒤 보고서·이어가기 절 근거까지 더한 903개)로 맞춘 규칙이고, 거기서 본문 오탐은 없었다.
본문으로 남기는 쪽으로 기운다 — 놓친 참고문헌은 지금과 같지만 잘못 거른 본문은 근거를 잃는다.
"""
import re

# 학술지 권호 — 참고문헌 항목에도 있지만 쪽 머리글('한국도서관·정보학회지(제45권 제2호)'·'… Vol. 45, No. 2')에도 쪽마다
# 찍힌다. 짧은 조각 갈래는 이 둘을 세지 않는다(_SHORT_SHAPES)
_VOLUME_KO = re.compile(r"제\s*\d+\s*(?:권|호|집)")                                      # 제35권 제2호
_VOLUME_EN = re.compile(r"\b(?:Vol|vol|VOL|No|no)\s*\.\s*\d")                            # Vol. 61
# 학위논문 — 항목의 학위 종류는 늘 문장부호가 잇는다('석사학위논문.'·'(박사학위논문).'·'석사학위논문, 고려대학교 대학원'·
# '석사학위논문, 2001.'). 본문의 '석사학위논문을 분석한'·사사 각주 '석사학위논문을 수정·보완한 것임'·'석사학위논문, 「제목」을'·
# '박사학위논문, 연세대학교 대학원(2010)의 일부를'(대학 이름 뒤가 괄호 연도·조사)과 표지의 '석사학위논문'(줄 끝)은 꼴이 아니다.
# OCR 이 낱자 사이를 띄우거나('석사학위논 문') 줄을 바꾼다('석사학위논\n\n문.'). 대학원 이름만으로는 꼴로 보지 않는다 — 첫 쪽
# 저자 소속 '* 연세대학교 대학원, 문헌정보학과 석사과정' 과 같은 꼴이다
_THESIS_KO = re.compile(
    r"[석박]\s*사\s*학\s*위\s*(?:청\s*구\s*)?논\s*문\s*"
    r"(?:[.)]|,\s*(?:[^,.\n]{0,20}?대\s*학\s*[교원](?!(?:[ \t]*[가-힣]*?대\s*학\s*원)?(?:[ \t]*\(|[의을를에]))"
    r"|(?:19|20)\d{2}(?![\d년])))")
# thesis, Hanyang University · Doctoral dissertation, University of Texas — 같은 줄에서 대학 이름이 이을 때만. 영문 사사
# 각주 'Based on the first author's master's thesis.' 는 꼴이 아니다
_THESIS_EN = re.compile(r"\b(?:[Tt]hesis|[Dd]issertation)[ \t]*[,.)]+[ \t]*[^,.;\n]{0,40}?\bUniv(?:ersity|\.)")
# 참고문헌 항목에 흔하고 본문 문장에는 드문 서지 꼴
_ENTRY_SHAPES = (
    re.compile(r"\bpp?\s*\.\s*\d"),                                                   # pp.402 · p. 12
    re.compile(r"\d{1,4}\s*\(\s*\d{1,3}(?:\s*[-,/·]\s*\d{1,3})?\s*\)\s*[,:.]"),        # 13(5), · 36(2):
    re.compile(r"\d{1,4}\s*(?:\(\s*\d{1,3}\s*\))?\s*:\s*\d{1,5}\s*[-–~∼～－]\s*\d{1,5}"),  # 23: 209-231 · 8(3) : 257-261
    re.compile(r"(?:19|20)\d{2}\s*;\s*\d+"),                                          # 1998;2:89 (밴쿠버)
    _VOLUME_KO,
    _VOLUME_EN,
    re.compile(r"\(\s*(?:19|20)\d{2}[a-z]?\s*\)\s*[.,:]"),                            # (2012). · (2000) :
    # , 2013. — 접수일 '접수 : 2010.' 과 날짜 '2006. 10. 4.' 는 서지의 연도가 아니다
    re.compile(r"(?<![\d.])(?<!:\s)(?<!:)(?:19|20)\d{2}[a-z]?\s*\.(?=\s|$)(?!\s*\d{1,2}\s*\.)"),
    re.compile(r"(?m)(?:^|\s)-?\s*\[\d{1,3}\]\s"),                                    # - [16] Norbeck
    re.compile(r"(?m)(?:^|\s-\s)\d{1,3}\)\s+[A-Z가-힣]"),                              # - 49) Camacho · 25) Lavretsky
    re.compile(r"[“\"「『󰡔][^”\"」』󰡕]{6,160}[”\"」』󰡕]\s*[,.]"),                        # “제목”, · 「제목」.
    re.compile(r"\b[A-Z][a-zA-Z'\-]+,\s*[A-Z]\.(?:\s*[A-Z]\.)?\s*(?:,|&|and\b|\()"),  # Selig, J. P., &
    re.compile(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)?\s[A-Z]{1,3},"),                       # Bruce ML, Seeman TE,
    _THESIS_KO,
    _THESIS_EN,
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
# '2016, Vol. 32, No. 4, pp. 183～204.'·그림 출처 '자료: 정효채 등. (2013). p.74' 는 꼴 여럿이 한 항목에 몰려 있다.
# 학술지 권호는 세지 않는다 — 문장이 잘린 본문 조각에서 쪽 머리글 '(제45권 제2호)' 와 직접 인용 '(김철수, 2010, p. 23)' 이
# 떨어져 있으면 꼴 두 종류·두 자리가 된다. 운영 근거 881개의 판정은 권호를 빼도 같다. 자리는 학위논문 꼴을 빼고 센 수와
# 넣고 센 수 가운데 큰 쪽이다 — 떨어진 두 꼴('20(1),'·'(2010).') 사이에 학위논문 꼴이 끼면 40자 안으로 이어져 한 자리로
# 묶이므로, 꼴을 더해 이미 걸리던 조각을 놓치지 않게
_SHORT_MAX = 300
_SPOT_GAP = 40
_SHORT_SHAPES = tuple(s for s in _ENTRY_SHAPES if s not in (_VOLUME_KO, _VOLUME_EN))
_SHORT_SHAPES_NO_THESIS = tuple(s for s in _SHORT_SHAPES if s not in (_THESIS_KO, _THESIS_EN))
# 참고문헌 꼬리 + 다음 쪽 영문 제목·초록 — 한국어 논문 끝 영문 초록 쪽이 참고문헌 마지막 쪽과 한 청크가 된 것. 앞 400자만
# 생성에 들어가 초록 대신 서지가 요약된다. 제 줄에 혼자 있는 'Abstract' 앞이 서술 없는 서지이고, 첫 제목 줄('#') 앞에
# 저자-연도 '(1996).' 가 있을 때만 본다 — 학술지 첫 쪽 머리의 'No. 3 (2017).' 는 저자 이니셜 뒤가 아니다. 첫 쪽 인용 안내
# 줄('Citation: Hong, G. D. (2017). …'·'How to cite this article: …')은 지우고 본다 — 이 논문 자신의 서지라, 논문 제목
# 줄보다 앞에 있거나 제목 줄이 없으면 그 청크의 초록까지 근거에서 빠진다
_ABSTRACT_LINE = re.compile(
    r"(?m)^[ \t]*(?:#{1,6}[ \t]*)?(?:&lt;|<|\[)?[ \t]*(?:Abstract|ABSTRACT)[ \t]*(?:&gt;|>|\])?[ \t]*$")
_AUTHOR_YEAR = re.compile(r"(?:\A|\b[A-Z]\.)\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)\s*[.,:]")
_HEADING_LINE = re.compile(r"(?m)^#{1,6}[ \t]")
_CITE_GUIDE_LINE = re.compile(
    r"(?im)^[ \t>*#-]*(?:citation\b|cite this\b|how to cite\b|to cite this\b|please cite\b|인용\s*[:：]|이 논문을 인용).*$")
_TAIL_BEFORE_ABSTRACT_MIN = 40
# 본문 끝 참고문헌 꼬리 — 맺음 문장 뒤(같은 줄의 '…필요를 느낀다. 참고문헌' 또는 제 줄의 '#### 참고문헌')에 머리와 첫 항목이
# 붙은 청크. 본문이라 근거로 남지만(looks_like_bibliography 는 False) 모델에 넘기는 대목에서는 머리 뒤를 뗀다. 머리는 줄
# 처음이나 문장 끝(마침표·닫는 따옴표·<br>) 바로 뒤에 있고, 머리 뒤에서 줄이 끝나야 한다(줄바꿈·<br>·글 끝). 같은 줄에 글이
# 이으면 문장 속 낱말일 수 있다 — '참고문헌 120편을 분석한 김철수(2010: 45-67)의'·'References [3] and [4] used' 는 낱말
# 검사를 지나고 뒤에 서지 꼴도 있어, 머리로 보면 그 뒤 본문을 모두 잃는다(운영 근거 903개에서 뗀 11개는 모두 머리 뒤가
# 줄바꿈이다). 줄 처음의 절 번호('Ⅵ. 참고문헌'·'## 7. References')는 머리와 함께 뗀다 — 번호 뒤 마침표에서 자르면 대목
# 끝에 'Ⅵ.' 이 매달린다. 쪽 배치가 뒤섞여 머리 뒤에 이 논문의 본문·그림 설명이 오는 청크가 있어(운영
# KCI_FI002782062__0044·KCI_FI001202853__0021) 머리 뒤 _TAIL_LOOK 자가 서술 없이 서지 꼴을 품을 때만 뗀다. 머리 앞에 서술이
# 없으면(목차·청크 맨 앞의 머리) 그대로 둔다
_SEP = r"(?:[ \t]|<br\s*/?>)"
_SECTION_NO = r"(?:#{1,6}[ \t]*)?(?:\d{1,2}|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]{1,2}|[IVX]{1,5})[ \t]*\.[ \t]*"
_TAIL_HEAD = re.compile(
    r"(?:^|(?<=[.。!?\"”’」』>]))" + _SEP + r"*((?:" + _SECTION_NO + r")?" + _HEAD_WORD + r")"
    r"(?=[ \t]*(?:<br\s*/?>|\r?\n|$))", re.M)
_TAIL_LOOK = 200
_TRAILING_SEP = re.compile(r"(?:\s|<br\s*/?>)+\Z")


def _spots(text: str, shapes: tuple[re.Pattern, ...]) -> int:
    """서지 꼴(shapes)이 놓인 자리 수 — _SPOT_GAP 안에 붙은 꼴은 한 자리로 센다."""
    spans = sorted(m.span() for shape in shapes for m in shape.finditer(text))
    spots, end = 0, float("-inf")
    for start, stop in spans:
        if start - end > _SPOT_GAP:
            spots += 1
        end = max(end, stop)
    return spots


def _entry_spots(text: str) -> int:
    """짧은 조각 갈래의 서지 꼴 자리 수 — 학위논문 꼴을 빼고 센 수와 넣고 센 수 가운데 큰 쪽."""
    return max(_spots(text, _SHORT_SHAPES_NO_THESIS), _spots(text, _SHORT_SHAPES))


def _no_prose(text: str) -> bool:
    return not _KOREAN_SENTENCE_END.search(text) and not _ENGLISH_PROSE.search(text)


def has_prose(text: str) -> bool:
    """서술 문장(한국어 서술 종결 또는 영어 서술 동사)이 하나라도 있는가 — 종합이 절 생성에 넘길 대목을 고를 때 쓴다."""
    return not _no_prose(text)


def strip_reference_tail(text: str) -> str:
    """본문 끝에 붙은 참고문헌 꼬리(머리와 그 뒤)를 뗀 글. 꼬리가 없으면 그대로 돌려준다.

    모델에 넘기는 대목(synthesizer._excerpt·research_work.passages)에 쓴다 — 400자 안의 짧은 대목이어도 맺음 문장 뒤의
    '참고문헌 고문희(2008), “노인우울증과 …”, … 석사학위논문.' 이 그 논문 내용처럼 읽힌다(운영 c816c7b2 E4). 근거 청크
    원문(인용칩 팝오버)은 바꾸지 않는다.
    """
    for m in _TAIL_HEAD.finditer(text):
        before, look = text[:m.start(1)], text[m.end(1):m.end(1) + _TAIL_LOOK]
        if not has_prose(before):
            continue
        if look.strip() and (has_prose(look) or not any(shape.search(look) for shape in _ENTRY_SHAPES)):
            continue
        return _TRAILING_SEP.sub("", before)
    return text


def _bibliography_before_abstract(text: str) -> bool:
    """제 줄의 'Abstract' 앞(인용 안내 줄을 뺀 글)이 참고문헌 꼬리인가 — 서술 0·서지 꼴 두 종류 이상·첫 제목 줄 앞의
    저자-연도."""
    abstract = _ABSTRACT_LINE.search(text)
    if not abstract or abstract.start() < _TAIL_BEFORE_ABSTRACT_MIN:
        return False
    before = _CITE_GUIDE_LINE.sub("", text[:abstract.start()])
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

    if (len(text) <= _SHORT_MAX and prose == 0
            and sum(1 for shape in _SHORT_SHAPES if shape.search(text)) >= _SHAPE_KINDS_MIN
            and _entry_spots(text) >= 2):
        return True
    if _bibliography_before_abstract(text):
        return True

    # 머리 없는 목록 — 같은 꼴 하나만 되풀이되는 글(번호 목록 '- 1)', 본문 번호 인용 ' [3] ', 법률 번호 '제8029호')은
    # 본문에도 있어 서로 다른 꼴이 둘 이상일 때만 목록으로 본다
    kinds = sum(1 for c in counts if c)
    return (entries >= _ENTRIES_MIN
            and entries * 1000 / len(text) >= _ENTRIES_PER_K_MIN
            and entries >= _ENTRIES_PER_PROSE * prose
            and kinds >= _SHAPE_KINDS_MIN)
