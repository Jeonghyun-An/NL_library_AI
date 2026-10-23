"""
표지 그림의 아트 디렉션 — 사진 종류·색 보정·구도는 코드가 정하고, LLM 은 '카메라가 무엇을 찍는지'(장면 한 문장)만 쓴다.

2026-10-23 대표 지적: 소장자료 표지가 다 비슷하다(재정 보고서마다 톱니·도시·빛줄기), 제목 기준 실사풍으로. 원인은 셋이었다.
  ① 표지 프롬프트가 모든 자료에 '상징적 은유'를 시켜 LLM 이 같은 그림으로 모였다(운영 gemma 로 24건 — 16건이 톱니·도시)
  ② 화풍·색을 LLM 이 골라 '푸른 회색·과슈'로 모였다
  ③ FLUX 에 건 e북 표지 LoRA 가 모든 그림을 같은 영화 포스터풍으로 끌었다(이건 FLUX 컨테이너 env 로 끈다)
그래서
  - 장르(정책·일반 / 고전문학 / 근현대문학)를 코드가 정하고 장르별 사진 종류·색 보정 목록에서 자료 id 해시로 고른다(축마다
    다른 소금 — 같은 자료는 늘 같은 값, 다시 만들어도 같은 사진 종류다)
  - 구도마다 장면 크기(object·vignette·wide)를 붙여 LLM 에 알린다 — 구도와 장면이 어긋나지 않게
  - 모든 자료가 실사 장면이다. 일반 재정 보고서(예산 지침·연간 계획·백서)는 예산이 닿는 실제 현장을 찍는다. 추상 그래픽 표지는
    두지 않는다(사용자 2026-10-23 — 대표는 전에 '너무 심오하다', 이번엔 '실사풍'을 원해 추상은 받아들여지지 않는다)
  - 완성 줄은 코드가 조립한다: '{사진 종류}: {장면} {구도} Colour grade: {색}. {글자 없는 장면}' — FLUX 는 부정 프롬프트를
    읽지 않으므로(우리 서버는 true_cfg 를 쓰지 않는다) 글자·간판을 막는 말도 긍정형 꼬리로 붙인다
  - 장면에 금지어(글자가 생기는 사물·상투 그림·재난의 아픈 장면)가 있으면 다시 쓰게 한다(cover_generator)
설계는 운영 gemma(Gemma 4)·FLUX.1-dev 로 24건 견본을 그려 비교해 골랐다(세션 scratchpad covers2 — 1회성).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# ── 장르별 사진 종류 (문구, 제 색이 있는 사진인가 — 흑백·세피아·손 채색처럼 색이 정해진 사진은 색 보정을 붙이지 않는다) ──
STYLES: dict[str, list[tuple[str, bool]]] = {
    "policy": [
        ("Editorial documentary photograph, natural daylight, 35mm lens, crisp detail", False),
        ("Aerial drone photograph looking straight down", False),
        ("Studio still-life photograph on a seamless coloured backdrop, softbox lighting, sharp focus", False),
        ("Wide landscape photograph in clear morning light", False),
        ("Macro close-up photograph with shallow depth of field and soft background blur", False),
        ("Architectural photograph with strong clean lines and corrected verticals", False),
        ("Tilt-shift miniature-effect photograph from a high viewpoint", False),
        ("Overcast documentary photograph with soft even light", False),
        ("High-key bright photograph with clean white surroundings", False),
        ("Low-angle photograph against an open sky, wide-angle lens", False),
        ("Golden-hour photograph with long warm shadows", False),
        ("Medium-format film photograph with fine grain", False),
    ],
    "classical": [
        ("Cinematic still from a Korean historical drama, natural light, shallow depth of field", False),
        ("Museum artifact photograph on a dark velvet background, gallery spot lighting", False),
        ("Documentary photograph of a preserved Joseon-era site, soft morning light", False),
        ("Still-life photograph of traditional Korean objects on plain hanji, soft window light", False),
        ("Landscape photograph of real Korean mountains and rivers, clear air", False),
        ("Cinematic wide still from a Korean period film, candle-lit interior", False),
        ("Close-up photograph of traditional craft textures, shallow depth of field", False),
        ("Overcast documentary photograph of a traditional village, muted natural colours", True),
    ],
    "modern": [
        ("Black-and-white film photograph in the style of 1930s press photography", True),
        ("Sepia-toned vintage photograph with soft vignetting", True),
        ("Cinematic still from a period drama set in early twentieth-century Korea, moody light", False),
        ("Hand-tinted antique photograph with faded colours", True),
        ("Documentary street photograph, available light, grainy film", False),
        ("Still-life photograph of period objects on a wooden table, soft window light", False),
        ("Medium-format film photograph with fine grain and muted colours", True),
        ("Low-light cinematic photograph lit by a single warm lamp", False),
    ],
}
# 장르별 색 보정
PALETTES: dict[str, list[str]] = {
    "policy": ["natural true-to-life colours", "warm golden film tones", "cool clean blue-grey tones", "soft muted pastel grade",
               "vivid saturated colours", "faded vintage film colours", "teal and amber cinematic grade", "crisp high-contrast colours"],
    "classical": ["warm candlelight tones", "soft natural colours of early morning", "muted earthy tones",
                  "deep rich colours with dark shadows", "pale cool tones", "warm autumn tones"],
    "modern": ["cool desaturated tones", "warm tungsten tones", "muted earthy tones", "soft faded colours"],
}
# (구도 문구, 장면 크기) — 넓은 장면은 셋뿐이다(작은 사람이 많은 파노라마는 검색 결과 썸네일에서 알아보기 어렵다)
COMPOSITIONS: list[tuple[str, str]] = [
    ("A single subject shown large and centred against a plain, uncluttered background.", "object"),
    ("Tight close-up crop, the frame edges cutting through the shapes.", "object"),
    ("Shown as a bold silhouette against a bright background.", "object"),
    ("Held up in a pair of anonymous hands entering from the bottom of the frame.", "object"),
    ("Viewed from directly overhead.", "vignette"),
    ("Strictly symmetrical, centred and balanced framing.", "vignette"),
    ("Strong diagonal line running from lower left to upper right.", "vignette"),
    ("Subject placed off-centre to the right, balanced by open space on the left.", "vignette"),
    ("A large foreground element overlaps the scene behind it, creating layered depth.", "vignette"),
    ("Everything sits in the lower third beneath a wide, calm sky.", "wide"),
    ("Low eye-level view, the main shape rising tall against the background.", "wide"),
    ("Wide view from a high vantage point with one dominant subject in the foreground.", "wide"),
]
SCALE_TEXT: dict[str, str] = {
    "object": "ONE object, creature or plant on its own (no surroundings beyond a hint of ground)",
    "vignette": "a small scene: one main subject with at most two supporting details",
    "wide": "a wide scene with ONE dominant subject large in the foreground and a simple setting behind it",
}
# 글자·간판이 생기지 않게 끝에 늘 붙이는 꼬리(긍정형 — FLUX 는 부정을 읽지 않는다)
TAIL = "Unlettered scene with clean unmarked surfaces."

# 고전·근현대 문학을 가르는 단서(제목·키워드·요약) — 많이 걸린 쪽으로, 같으면 근현대. 한글 두 글자 단서는 뜻이 갈려 쓰지 않는다
# ('시가'=시+가·市街, '고려'=고려하다, '고전'=서양 고전 명작, '한시'=한시적 — 리뷰 지적 2026-10-23). 한자·여러 글자 갈래 이름만 쓴다
CLASSICAL_CUES = re.compile(
    r"朝鮮|조선|古典|고전소설|고전문학|고전시가|詩歌|歌辭|樓亭|누정|高麗|고려가요|고려시대|漢詩|時調|시조|판소리|傳奇|전기소설|"
    r"가전체|夢遊|몽유록|士大夫|사대부|儒|유교|성리|性理|三國|삼국시대|新羅|신라")
MODERN_CUES = re.compile(r"近代|근대|現代|현대|新小說|신소설|19[0-9]0|年代|년대|모더니즘|해방|일제|開化|개화")
# 재난 자료 — 배·물에 뜬 물건을 더 막는다. '안전'(사회안전망)·'사고'(思考)는 재난이 아닌 제목에도 있어 쓰지 않는다
DISASTER_TITLE = re.compile(r"재난|재해|災|참사|붕괴|홍수|태풍|지진|화재|산불")

# 장면에 들어가면 안 되는 말 — 글자가 생기는 사물, 상투 그림, 아픈 장면. 걸리면 다시 쓰게 한다.
# 낱말 단위로 맞춘다(복수·-ing·-ed 따위 꼬리만 허용) — 접두 일치는 'European'→euro, 'maple'→map 처럼 흔한 말을 잡았다
BANNED_WORDS: list[str] = [
    "book", "page", "paper", "file", "ledger", "letter", "lettering", "scroll", "calligraphy", "calligrapher", "newspaper",
    "map", "blueprint", "chart", "graph", "calendar", "sign", "signboard", "signage", "banner", "screen", "monitor", "coin",
    "banknote", "money", "stamp", "seal", "label", "ticket", "printing", "flag", "emblem", "office", "meeting", "conference",
    "desk", "suit", "excavator", "bulldozer", "hard hat", "gear", "cog", "clockwork", "skyline", "skyscraper", "cityscape",
    "city", "cities", "beam of light", "ray", "glow", "orb", "vortex", "swirl", "maze", "hourglass", "light bulb", "lightbulb",
    "puzzle", "chess", "scales", "door", "doorway", "gate", "gateway", "path", "road", "bridge", "stair", "staircase",
    "compass", "vault", "tower", "station", "bus stop", "podium", "sprout", "seedling", "paper crane", "lantern", "mist",
    "scholar", "marketplace", "shipping container", "cargo", "harbour crane", "harbor crane", "sack", "tea bowl", "fan",
    "lacquer box", "plum branch", "bamboo grove", "robe", "pine tree", "peach", "fruit bowl", "barrel", "crate", "dial",
    "monument", "plaque", "statue",
    # 실사 견본(2026-10-23)에서 글자가 찍혔다 — 손에 든 카드(신분증 같은 글씨), 인쇄기 옆 종이
    "card", "id card", "badge", "printing press", "hand press", "typewriter",
    # 화폐 이름은 FLUX 가 글자로 그린다(2026-10-23 견본 — 'Euro banknote-shaped chocolate' 에 'EURO' 가 찍혔다)
    "euro", "dollar", "currency", "currencies",
    # 구명조끼·구명튜브는 세월호를 떠올리게 한다(2026-10-23 실사 견본에서 재난연감·나라살림 장면에 나왔다) — 모든 자료에서 막는다
    "victim", "corpse", "drown", "capsize", "capsizing", "wreck", "wreckage", "lifebuoy", "life jacket", "life vest",
    "life ring",
]
_SUFFIX = r"(?:s|es|ies|y|e|d|ed|ing|ings)?"
_BANNED_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED_WORDS) + r")" + _SUFFIX + r"\b", re.I)
# 재난 자료에서만 더 막는 말 — 배·물에 뜬 물건은 세월호를 떠올리게 한다(2026-10-23 견본에서 '옆으로 누운 여객선'이 나왔다).
# 합성어(lifeboat·warship·sailboat)도 잡는다
_DISASTER_RE = re.compile(
    r"\b(\w*(?:boat|ship|ferry|ferries|vessel)s?|sink|sinking|sank|sunk|tilt|tilted|tilting|overturn|overturned|"
    r"floating|flood ?water)\b", re.I)

# 장면 끝의 의미 풀이('…, representing resilience') — 상징물을 부르고 그림에 쓸모없다.
# 'reflecting the …'는 물에 비친 모습 같은 실제 묘사일 수 있어 두다(리뷰 지적)
_MEANING_TAIL = re.compile(
    r"[,;]?\s*\b(representing|symbolizing|symbolising|signifying|evoking|suggesting|embodying)\b.*$", re.I)
# 목적·관계절의 의미 풀이('… to represent the five years') — reflect·mirror·show 는 실제 묘사일 수 있어 두다
_MEANING_MID = re.compile(
    r"\s*,?\s*\b(?:to|that|which)\s+(?:represent|symboli[sz]e|signify|denote|stand for)s?\b[^,;]*?(?=[,;]|\.\s|\.$|$)",
    re.I)
# 홀로 선 숫자·퍼센트는 FLUX 가 글자로 그린다('98.8%'). '1930s'·'18th-century' 처럼 낱말에 붙은 숫자는 두다(반만 지우면 문장이 깨졌다)
_DIGITS = re.compile(r"\(?(?<![\w-])\d+(?:[.,]\d+)*\s?%?(?![\w-])\)?")


@dataclass(frozen=True)
class ArtDirection:
    genre: str          # policy | classical | modern
    style: str          # 사진 종류
    own_colour: bool    # 흑백·세피아처럼 색이 정해진 사진 — 색 보정을 붙이지 않는다
    palette: str        # 색 보정
    composition: str
    scale: str          # object | vignette | wide


def _pick(book_id: str, salt: str, n: int) -> int:
    return int(hashlib.sha1(f"{salt}:{book_id}".encode()).hexdigest(), 16) % n


def genre_of(doc_type: str | None, title: str = "", themes: str = "", summary: str = "") -> str:
    """문학이면 고전·근현대를 단서 수로 가르고, 그 밖(정책·일반 도서)은 policy."""
    if (doc_type or "") != "literature":
        return "policy"
    text = " ".join([title or "", themes or "", summary or ""])
    return "classical" if len(CLASSICAL_CUES.findall(text)) > len(MODERN_CUES.findall(text)) else "modern"


def art_direction(book_id: str, doc_type: str | None, title: str = "", themes: str = "", summary: str = "") -> ArtDirection:
    genre = genre_of(doc_type, title, themes, summary)
    style, own_colour = STYLES[genre][_pick(book_id, "style", len(STYLES[genre]))]
    palette = PALETTES[genre][_pick(book_id, "palette", len(PALETTES[genre]))]
    composition, scale = COMPOSITIONS[_pick(book_id, "composition", len(COMPOSITIONS))]
    return ArtDirection(genre, style, own_colour, palette, composition, scale)


def banned_terms(scene: str, title: str = "") -> list[str]:
    """장면에 든 금지어(소문자, 겹침 없이) — 재난 자료는 배·물에 뜬 물건도 막는다."""
    hits = {m.group(1).lower() for m in _BANNED_RE.finditer(scene or "")}
    if DISASTER_TITLE.search(title or ""):
        hits |= {m.group(1).lower() for m in _DISASTER_RE.finditer(scene or "")}
    return sorted(hits)


def clean_scene(text: str) -> str:
    """LLM 이 쓴 장면 한 문장을 다듬는다 — 머리표·따옴표·둘째 줄·의미 풀이·홀로 선 숫자를 걷고 마침표로 끝낸다."""
    s = (text or "").strip().strip('"').strip()
    s = re.sub(r"^(scene\s*:\s*)", "", s, flags=re.I).strip().strip('"')
    s = s.split("\n")[0].strip()
    s = _MEANING_TAIL.sub("", s).strip()
    s = _MEANING_MID.sub("", s).strip()
    s = _DIGITS.sub("", s)
    s = re.sub(r"\s{2,}", " ", re.sub(r"\s+([,.;])", r"\1", s)).strip()
    s = s.rstrip(".,; ")
    return f"{s}." if s else ""


def assemble(ad: ArtDirection, scene: str) -> str:
    """완성 프롬프트 한 줄 — 사진 종류: 장면 구도 색 보정. 글자 없는 장면."""
    grade = "" if ad.own_colour else f" Colour grade: {ad.palette}."
    return f"{ad.style}: {scene} {ad.composition}{grade} {TAIL}"


def key_nouns(scene: str, n: int = 4) -> str:
    """같은 묶음의 다음 표지에 '이미 쓴 소재'로 넘길 앞 몇 낱말(관사·전치사·크기 말 빼고)."""
    skip = {"a", "an", "the", "of", "with", "on", "in", "and", "at", "by", "from", "its", "their", "two", "three",
            "small", "large", "single", "solitary", "lone", "wide", "tall", "old", "new"}
    words = [w for w in re.findall(r"[A-Za-z-]+", scene or "") if w.lower() not in skip]
    return " ".join(words[:n])
