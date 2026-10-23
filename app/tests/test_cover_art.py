"""표지 아트 디렉션(cover_art)·표지 프롬프트 만들기(cover_generator.compose_cover)·다시 만들기 스크립트의 순수 부분.

2026-10-23 대표 지적('소장자료 표지가 다 비슷하다', 제목 기준 실사풍) — 사진 종류·색 보정·구도는 코드가 자료 id 로 고르고,
LLM 은 카메라가 찍을 장면 한 문장만 쓴다. 장면의 금지어는 걸린 말을 알려 두 번까지 다시, 그래도 남은 문학 아닌 자료는
표지를 만들지 않는다(옛 표지를 둔다)."""
import asyncio

import pytest

import services.llm_client as llm_client
from scripts import regenerate_covers as regen
from services.ingestion import cover_art
from services.ingestion.cover_generator import COVER_PROMPT_MAX_CALLS, compose_cover, generate_cover_prompt


# ── 장르 ───────────────────────────────────────────────────
def test_genre_policy_unless_literature():
    assert cover_art.genre_of("policy", "2005 나라살림") == "policy"
    assert cover_art.genre_of("book", "아시아 국제금융중심지로서의 한국") == "policy"
    assert cover_art.genre_of(None, "제목") == "policy"


def test_genre_literature_classical_or_modern_by_cues():
    assert cover_art.genre_of("literature", "蘆溪 朴仁老의 詩歌硏究", "유교적 가치관, 충군") == "classical"
    assert cover_art.genre_of("literature", "조선조 가정소설 연구", "일부다처제, 유교적 이데올로기") == "classical"
    assert cover_art.genre_of("literature", "1930年代 韓國 心理小說 硏究", "모더니즘, 의식의 흐름") == "modern"
    assert cover_art.genre_of("literature", "金東里 小說 硏究", "무당, 죽음 의식") == "modern"  # 단서가 같으면(0:0) 근현대


# 리뷰 지적 — 한글 두 글자 단서('시가'=시+가, '고려'=고려하다, '고전'=서양 고전 명작)가 근현대·서양 문학을 고전으로 보냈다
@pytest.mark.parametrize("title, themes", [
    ("현대 서양 고전 명작의 서사 연구", "모더니즘"),
    ("김수영의 시가 지닌 현실 인식", "참여시"),
    ("독자를 고려한 근대 소설의 문체", "근대 독자"),
])
def test_ambiguous_hangul_words_are_not_classical_cues(title, themes):
    assert cover_art.genre_of("literature", title, themes) == "modern"


# ── 고르기 ─────────────────────────────────────────────────
def test_art_direction_is_stable_per_id_and_spreads_over_the_lists():
    a = cover_art.art_direction("CNTS-1", "policy", "2005 나라살림")
    assert a == cover_art.art_direction("CNTS-1", "policy", "2005 나라살림")  # 다시 만들어도 같은 사진 종류
    picks = [cover_art.art_direction(f"CNTS-{n:05d}", "policy", "2004 재난연감") for n in range(400)]
    assert {p.style for p in picks} == {s for s, _ in cover_art.STYLES["policy"]}
    assert {p.palette for p in picks} == set(cover_art.PALETTES["policy"])
    assert {p.composition for p in picks} == {c for c, _ in cover_art.COMPOSITIONS}


def test_every_style_is_a_photograph():
    for genre, styles in cover_art.STYLES.items():
        for style, _ in styles:
            assert "photograph" in style.lower() or "still from" in style.lower(), (genre, style)


# v8(2026-10-23) — 정물·접사·스튜디오 사진 종류와 사물 하나만 두는 구도가 흙 위의 비녀·도랑 속 밸브 같은 표지를 냈다
def test_styles_and_compositions_always_frame_a_scene():
    for genre, styles in cover_art.STYLES.items():
        for style, _ in styles:
            low = style.lower()
            assert not any(w in low for w in ("still-life", "still life", "macro", "close-up", "studio", "museum",
                                              "tilt-shift", "high-key")), (genre, style)
    assert {scale for _, scale in cover_art.COMPOSITIONS} == set(cover_art.SCALE_TEXT) == {"vignette", "wide"}


def test_classical_styles_come_from_the_classical_list():
    picks = {cover_art.art_direction(f"L{n}", "literature", "朝鮮初期 樓亭記의 硏究").style for n in range(100)}
    assert picks <= {s for s, _ in cover_art.STYLES["classical"]}


# ── 금지어 ─────────────────────────────────────────────────
def test_banned_terms_catch_text_bearing_and_cliche_subjects():
    assert cover_art.banned_terms("A brass compass beside a glowing orb") == ["compass", "glow", "orb"]
    assert cover_art.banned_terms("a city skyline at dusk") == ["city", "skyline"]
    assert cover_art.banned_terms("An embankment reinforced with sandbags by crews") == []
    assert cover_art.banned_terms("A Euro banknote-shaped piece of chocolate") == ["banknote", "euro"]  # FLUX 가 'EURO' 를 썼다
    assert cover_art.banned_terms("A stack of orange life vests on a pier") == ["life vest"]


# 리뷰 지적 — 접두 일치가 흔한 말을 잡았다('European'→euro, 'maple'→map, 'array'→ray, 'fancy'→fan, 'signal'→sign)
def test_banned_terms_match_whole_words_not_prefixes():
    assert cover_art.banned_terms("a maple tree in a European square with an array of fancy signal lamps") == []
    assert cover_art.banned_terms("Signs and maps") == ["map", "sign"]          # 복수는 잡는다
    assert cover_art.banned_terms("a glowing calligraphy scroll") == ["calligraphy", "glow", "scroll"]
    # 'gear' 하나는 옷·장비(waterproof gear)라 두고, 톱니(gears·cogwheel)만 막는다. 컴퓨터는 화면 글자가 찍힌다
    assert cover_art.banned_terms("workers in waterproof gear adjusting a pump") == []
    assert cover_art.banned_terms("brass gears and a cogwheel") == ["cogwheel", "gears"]
    assert cover_art.banned_terms("citizens at a row of computers") == ["computer"]


def test_disaster_titles_also_ban_boats_and_floating_things_including_compounds():
    scene = "A tilted passenger ferry resting on its side surrounded by lifebuoys"
    assert "lifebuoy" in cover_art.banned_terms(scene)                              # 어디서나
    assert {"ferry", "tilted"} <= set(cover_art.banned_terms(scene, "2004 재난연감"))  # 재난 자료에서만
    assert cover_art.banned_terms("A fishing boat in a bay", "조선조 가정소설 연구") == []
    assert cover_art.banned_terms("A fishing boat in a bay", "2004 재난연감") == ["boat"]
    # 합성어도(리뷰 지적 — lifeboat·warship 가 지나갔다)
    assert cover_art.banned_terms("Crews launching a lifeboat near a warship", "2004 재난연감") == ["lifeboat", "warship"]
    # 무너진 건물·잔해도 재난 자료에서만(v8 견본 — '무너진 아파트 잔해 속 구조대')
    scene = "Rescue workers move through the rubble of a collapsed apartment block"
    assert cover_art.banned_terms(scene, "2004 재난연감") == ["collapsed", "rubble"]
    assert cover_art.banned_terms(scene, "조선조 가정소설 연구") == []


# 리뷰 지적 — '안전'(사회안전망)·'사고'(思考)는 재난이 아닌 제목에도 있다
def test_disaster_title_does_not_fire_on_safety_net_or_thought():
    assert cover_art.banned_terms("A fishing boat in a bay", "사회안전망 확충 방안") == []
    assert cover_art.banned_terms("A fishing boat in a bay", "실학 사상과 사고의 전환") == []


# ── 다듬기·조립 ────────────────────────────────────────────
@pytest.mark.parametrize("raw, want", [
    ('"Scene: A dam under construction in a valley."', "A dam under construction in a valley."),
    ("A single pine on a rock, representing resilience.", "A single pine on a rock."),
    ("Five rings in a tight cluster to represent the five years of reform, with the outer ring in red.",
     "Five rings in a tight cluster, with the outer ring in red."),
    ("Stripes in an ascending sequence with the 98.8% execution rate, and one bright stripe.",
     "Stripes in an ascending sequence with the execution rate, and one bright stripe."),
    # 리뷰 지적 — 실제 묘사인 '비친다'는 두고, 낱말에 붙은 숫자('1930s'·'18th-century')는 반만 지우지 않는다
    ("A stone basin filled with rainwater reflecting the surrounding mountains.",
     "A stone basin filled with rainwater reflecting the surrounding mountains."),
    ("A 1930s Seoul street corner with an 18th-century gate post, in 1999, quiet.",
     "A 1930s Seoul street corner with an 18th-century gate post, in, quiet."),
    ("A lotus on still water\nSecond line ignored", "A lotus on still water."),
    ("", ""),
])
def test_clean_scene(raw, want):
    assert cover_art.clean_scene(raw) == want


def test_assemble_photo_line_and_own_colour_styles_skip_the_grade():
    ad = cover_art.ArtDirection("policy", "Aerial drone photograph looking straight down", False, "warm golden film tones",
                                "Viewed from directly overhead.", "vignette")
    assert cover_art.assemble(ad, "A dam in a valley.") == (
        "Aerial drone photograph looking straight down: A dam in a valley. "
        "Photographed in South Korea, with Korean people and Korean surroundings. Viewed from directly overhead. "
        "Colour grade: warm golden film tones. Any people are anonymous, small in the frame or turned away. "
        "Unlettered scene with clean unmarked surfaces.")
    bw = cover_art.ArtDirection("modern", "Black-and-white film photograph", True, "warm tungsten tones",
                                "Everything sits in the lower half beneath a wide, calm sky.", "wide")
    assert "Colour grade" not in cover_art.assemble(bw, "A streetcar.")


def test_key_nouns_skip_articles_and_size_words():
    assert cover_art.key_nouns("A single weathered stone pagoda in a quiet Gyeongju forest.") == "weathered stone pagoda quiet"


# ── compose_cover (LLM 은 가짜) ───────────────────────────
def _fake_chat(monkeypatch, answers):
    """차례로 답하는 가짜 chat — 받은 유저 프롬프트를 calls 에 남긴다. 예외를 넣으면 그 차례에 던진다."""
    calls = []

    async def fake(messages, *, params=None, timeout=120.0, **kw):
        calls.append(messages[1]["content"])
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(llm_client, "chat", fake)
    return calls


def _compose(**kw):
    base = dict(title="t", author="a", kdc="", themes="", introduction="", summary="요약", book_id="CNTS-1", doc_type="policy")
    base.update(kw)
    return asyncio.run(compose_cover(**base))


def test_scene_becomes_a_photo_line_and_the_scene_comes_back_separately(monkeypatch):
    _fake_chat(monkeypatch, ["Rescue crews stacking sandbags on a levee, representing resilience."])
    prompt, scene = _compose(title="2004 재난연감")
    assert scene == "Rescue crews stacking sandbags on a levee."
    assert scene in prompt and prompt.endswith(cover_art.TAIL) and "representing" not in prompt


def test_banned_scene_is_rewritten_with_the_hits(monkeypatch):
    calls = _fake_chat(monkeypatch, ["A brass compass on a pier.", "Rescue crews stacking sandbags on a levee."])
    prompt, _ = _compose(title="2004 재난연감")
    assert len(calls) == 2 and "Your previous scene was: A brass compass on a pier." in calls[1] and "(compass)" in calls[1]
    assert "Rescue crews stacking sandbags on a levee." in prompt


def test_still_banned_after_all_calls_policy_gets_no_cover(monkeypatch):
    calls = _fake_chat(monkeypatch, ["A tilted ferry.", "A sinking ferry at dusk.", "A ferry beside a pier."])
    assert _compose(title="2004 재난연감") is None          # 옛 표지를 둔다 — 배·물에 뜬 물건을 내보내지 않는다
    assert len(calls) == COVER_PROMPT_MAX_CALLS


def test_literature_keeps_its_scene_when_still_banned(monkeypatch):
    _fake_chat(monkeypatch, ["A scholar in robes by a pond.", "A scholar in robes under a willow.", "A scholar in robes at dusk."])
    prompt, _ = _compose(title="조선조 가정소설 연구", doc_type="literature", themes="유교")
    assert "A scholar in robes" in prompt  # 문학은 버리지 않는다(금지어는 기록만)


# 리뷰 지적 — 다시 쓰기 호출이 실패하면 멀쩡한 첫 장면까지 버렸다
def test_failed_retry_call_keeps_the_previous_scene(monkeypatch):
    _fake_chat(monkeypatch, ["A scholar in robes by a pond.", RuntimeError("LLM down")])
    prompt, _ = _compose(title="조선조 가정소설 연구", doc_type="literature")
    assert "A scholar in robes by a pond." in prompt


def test_avoid_list_reaches_the_scene_prompt(monkeypatch):
    calls = _fake_chat(monkeypatch, ["Rescue crews on a levee."])
    _compose(title="2004 재난연감", avoid=["stone pagoda", "white lotus"])
    assert "choose something different): stone pagoda, white lotus" in calls[0]


def test_empty_answer_gives_no_cover_and_generate_cover_prompt_returns_the_line(monkeypatch):
    _fake_chat(monkeypatch, [""])
    assert _compose(title="2001년도 예산안편성지침 및 기준") is None
    _fake_chat(monkeypatch, ["A rural clinic courtyard with a parked ambulance."])
    line = asyncio.run(generate_cover_prompt("2005 나라살림", "a", "", "", "", "요약", book_id="X", doc_type="policy"))
    assert line and "A rural clinic courtyard with a parked ambulance." in line


# ── 다시 만들기 스크립트의 순수 부분 ─────────────────────────
def test_done_parts_reads_only_finished_rows_and_old_rows_are_photo(tmp_path):
    log = tmp_path / "run.jsonl"
    log.write_text('{"cnts_id": "A", "status": "ok"}\n{"cnts_id": "B", "status": "fail", "made": ["typo"]}\nnot json\n'
                   '{"cnts_id": "C", "status": "dry", "made": ["photo"]}\n{"cnts_id": "D", "status": "kept_old"}\n'
                   '{"cnts_id": "P", "status": "ok", "made": ["typo"]}\n{"cnts_id": "P", "status": "ok", "made": ["photo"]}\n',
                   encoding="utf-8")
    assert regen.done_parts(str(log)) == {"A": {"photo"}, "P": {"typo", "photo"}}
    assert regen.done_parts(str(tmp_path / "none.jsonl")) == {}
    assert regen.done_parts("") == {}


# 리뷰 지적 — limit 을 끝낸 자료를 빼기 전에 걸어, 같은 기록으로 나눠 돌리면 첫 묶음만 되풀이했다
def test_pending_skips_done_before_limit():
    targets = [{"cnts_id": c, "doc_type": "literature"} for c in "ABCDE"]
    done = {"A": {"photo"}, "B": {"photo"}}
    assert [t["cnts_id"] for t in regen.pending(targets, done, 2)] == ["C", "D"]
    assert [t["cnts_id"] for t in regen.pending(targets, {}, 0)] == list("ABCDE")


# 정책 보고서는 목업·그림 두 판 — 목업만 먼저 돌린 자료도 그림 판을 돌릴 때는 다시 대상이 된다
def test_policy_needs_the_requested_parts_and_others_only_the_photo():
    assert regen.needed_parts("policy", {"typo", "photo"}) == {"typo", "photo"}
    assert regen.needed_parts("literature", {"typo"}) == {"photo"}
    targets = [{"cnts_id": "P", "doc_type": "policy"}, {"cnts_id": "L", "doc_type": "literature"}]
    done = {"P": {"typo"}, "L": {"photo"}}
    assert [t["cnts_id"] for t in regen.pending(targets, done, 0, {"typo"})] == []
    assert [t["cnts_id"] for t in regen.pending(targets, done, 0, {"typo", "photo"})] == ["P"]


def test_shown_key_prefers_the_show_version_then_the_other():
    both = lambda v: True                       # noqa: E731
    only_photo = lambda v: v == "photo"         # noqa: E731
    assert regen.shown_key("P", "policy", "typo", both) == "covers/typo/P.jpg"
    assert regen.shown_key("P", "policy", "typo", only_photo) == "covers/P.jpg"
    assert regen.shown_key("P", "policy", "photo", both) == "covers/P.jpg"
    assert regen.shown_key("L", "literature", "typo", both) == "covers/L.jpg"   # 문학·도서는 늘 그림
    assert regen.shown_key("L", "literature", "photo", lambda v: False) is None


def test_args_default_to_a_dry_run_with_backups_and_a_failure_stop():
    args = regen.parse_args([])
    assert not args.apply and not args.no_backup and args.max_fails == 5
    assert args.doc_types.split(",") == ["policy", "literature", "book"]
    assert args.parts == {"typo", "photo"} and args.show == "typo" and not args.switch
    assert regen.parse_args(["--parts", "typo"]).parts == {"typo"}
    with pytest.raises(SystemExit):
        regen.parse_args(["--parts", "abstract"])


# ── generate_and_store_cover — 정책 보고서는 목업·그림 둘 다(그림 쪽은 가짜) ──────────
class _FakeMinio:
    def __init__(self, fail_prefix: str = ""):
        self.keys: list[str] = []
        self.fail_prefix = fail_prefix

    def put_object(self, bucket, key, data, length, content_type):
        if self.fail_prefix and key.startswith(self.fail_prefix):
            raise RuntimeError("MinIO down")
        self.keys.append(key)


def _store(monkeypatch, doc_type, client, photo=("covers/X.jpg", "a photo prompt")):
    from services.ingestion import cover_generator

    async def fake_photo(*a, **kw):
        if photo[0]:
            client.keys.append(photo[0])
        return photo

    monkeypatch.setattr(cover_generator, "_generate_photo_cover", fake_photo)
    return asyncio.run(cover_generator.generate_and_store_cover(
        book_id="X", title="2005 나라살림", author="", kdc="329", themes="", introduction="", summary="요약",
        minio_client=client, doc_type=doc_type, publisher="기획예산처"))


def test_policy_makes_both_versions_and_shows_the_typo(monkeypatch):
    client = _FakeMinio()
    assert _store(monkeypatch, "policy", client) == ("covers/typo/X.jpg", "a photo prompt")
    assert sorted(client.keys) == ["covers/X.jpg", "covers/typo/X.jpg"]


def test_literature_and_books_make_only_the_photo(monkeypatch):
    for doc_type in ("literature", "book", None):
        client = _FakeMinio()
        assert _store(monkeypatch, doc_type, client) == ("covers/X.jpg", "a photo prompt")
        assert client.keys == ["covers/X.jpg"]


def test_policy_falls_back_to_the_other_version(monkeypatch):
    # 목업이 실패하면 그림, 그림이 없으면(금지어·소개 없음) 목업
    assert _store(monkeypatch, "policy", _FakeMinio(fail_prefix="covers/typo/")) == ("covers/X.jpg", "a photo prompt")
    assert _store(monkeypatch, "policy", _FakeMinio(), photo=(None, None)) == ("covers/typo/X.jpg", None)
