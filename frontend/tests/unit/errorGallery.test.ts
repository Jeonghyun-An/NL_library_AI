// frontend/tests/unit/errorGallery.test.ts
// 오류 화면 모음(/dev/error-states)과 그것이 보이는 새 공통 표시 — 연결 끊김 띠(SkxConnectionBanner)·글자 수(SkxCharCount)·
// 전역 오류 화면 본문(SkxErrorPage preview). 컴포넌트는 Nuxt 를 띄우지 않고 소스 글을 검사하고(기존 관례),
// 글자 수 상태 셈(charCountState)처럼 순수 함수로 뺀 것은 실제로 돌린다
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  CONNECTION_HINTS,
  CONNECTION_RETRY_LABEL,
  VALIDATION_HINTS,
  apiErrorMessage,
  charCountState,
  charLimitMessage,
  errorKind,
} from "~/utils/apiErrors";
import { BOOK_DETAIL_TEXT, BOOK_REASON_TEXT, BOOK_SEARCH_TEXT, SCENARIO_TEXT, failureView } from "~/utils/bookErrors";
import { CHAT_MAX_CHARS } from "~/utils/deepReadSse";
import { rawCss } from "./helpers/themeCss";

const root = resolve(__dirname, "../..");
// 줄 끝은 \n 으로 맞춘다 — Windows 체크아웃(autocrlf)은 CRLF 라 줄 경계를 보는 정규식이 체크아웃마다 달라진다
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8").replace(/\r\n/g, "\n");

const bannerVue = read("components/SkxConnectionBanner.vue");
const countVue = read("components/SkxCharCount.vue");
const pageVue = read("components/SkxErrorPage.vue");
const galleryVue = read("pages/dev/error-states.vue");

/** <template> 부분만 — 머리 주석의 글에 속지 않게 */
const template = (src: string) => src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? "";
const script = (src: string) => src.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)?.[1] ?? "";
const style = (src: string) => src.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? "";

/** 색 리터럴(#hex·rgb()·hsl()·색 이름·currentColor) — 주석을 지운 CSS 에서 찾는다 */
const colorLiterals = (cssText: string) =>
  cssText
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(|(?<![\w-])(?:white|black|red|green|blue|gray|grey|currentcolor)(?![\w-])/gi) ?? [];

describe("SkxConnectionBanner — 실시간 연결 끊김 띠", () => {
  const tpl = template(bannerVue);
  const js = script(bannerVue);

  it("문구 — 다시 연결하는 중 / 연결하지 못함 + [다시 연결], 붙어 있으면 빈 글", () => {
    expect(CONNECTION_HINTS).toEqual({
      reconnecting: "연결이 끊겨 다시 연결하는 중이에요…",
      lost: "연결하지 못했어요.\n화면이 최신 상태가 아닐 수 있어요.",
    });
    expect(CONNECTION_RETRY_LABEL).toBe("다시 연결");
    expect(js).toContain('const message = computed(() => (props.state === "connected" ? "" : CONNECTION_HINTS[props.state]));');
    expect(tpl).toContain('<span class="skx-conn__msg">{{ message }}</span>');
    expect(tpl).toContain("{{ CONNECTION_RETRY_LABEL }}");
  });

  it("디자인 훅 — .skx-conn·.skx-conn--{state}·data-state", () => {
    expect(tpl).toContain('class="skx-conn"');
    expect(tpl).toContain(':class="`skx-conn--${state}`"');
    expect(tpl).toContain(':data-state="state"');
  });

  it("알림 영역은 늘 그려 두는 한 영역(role=status) — 상태가 바뀌어도 role 을 바꾸지 않고, 붙어 있으면 안을 비운다(쓰는 화면이 늘 그려 두고 state 만 바꾼다)", () => {
    expect(tpl).toMatch(/<div\s+ref="root"\s+class="skx-conn"[\s\S]*?role="status"\s+tabindex="-1"\s*>/);
    expect(tpl).not.toContain(":role=");
    expect(tpl).toContain('<template v-if="message">');
    expect(js).toMatch(/state: ConnectionState;/);
    // 머리 주석에 사용법(늘 그려 두고 state 만 바꾼다)
    expect(bannerVue).toContain("쓰는 화면은 띠를 늘 그려 두고 state 만 바꾼다");
    expect(bannerVue).toContain("(v-if 로 끊길 때만 그리지 않는다)");
  });

  it("[다시 연결] 은 lost 이고 부모가 @retry 를 달았을 때만", () => {
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(js).toContain('import { CONNECTION_HINTS, CONNECTION_RETRY_LABEL, type ConnectionState } from "~/utils/apiErrors"');
    expect(tpl).toMatch(/<button v-if="state === 'lost' && onRetry" ref="retryButton" type="button" class="skx-conn__retry" @click="onRetry\?\.\(\)">/);
  });

  it("[다시 연결] 이 사라질 때(state 가 lost 에서 바뀜) 그 버튼에 있던 초점을 띠(tabindex=-1)로 옮긴다 — body 로 빠지지 않게", () => {
    expect(js).toMatch(
      /watch\(\s*\(\) => props\.state,\s*async \(next\) => \{\s*if \(next === "lost" \|\| typeof document === "undefined"\) return;\s*const button = retryButton\.value;\s*if \(!button \|\| document\.activeElement !== button\) return;\s*await nextTick\(\);\s*root\.value\?\.focus\(\);/,
    );
  });
});

describe("SkxCharCount — 글자 수", () => {
  const tpl = template(countVue);
  const js = script(countVue);

  it("상태 셈 — 한도(length >= max)·가까움(기본 max 의 90%, 버림)·평소", () => {
    expect(charCountState(120, 500)).toBe("normal");
    expect(charCountState(449, 500)).toBe("normal");
    expect(charCountState(450, 500)).toBe("near");
    expect(charCountState(460, 500)).toBe("near");
    expect(charCountState(499, 500)).toBe("near");
    expect(charCountState(500, 500)).toBe("limit");
    expect(charCountState(520, 500)).toBe("limit");
    // 0.9 곱셈의 부동소수 오차(459.00000000000006)에 459 가 '평소'로 떨어지지 않는다
    expect(charCountState(459, 510)).toBe("near");
    expect(charCountState(458, 510)).toBe("normal");
    // near 를 주면 그 값부터
    expect(charCountState(300, 500, 300)).toBe("near");
    expect(charCountState(299, 500, 300)).toBe("normal");
  });

  it("한도 안내는 서버 422(string_too_long)와 같은 말", () => {
    expect(charLimitMessage(500)).toBe("500자까지 입력할 수 있어요");
    expect(charLimitMessage(500)).toBe(VALIDATION_HINTS.tooLong.replace("{n}", "500"));
    expect(
      apiErrorMessage({ status: 422, data: { detail: [{ type: "string_too_long", ctx: { max_length: 500 } }] } }, "검색하지 못했어요"),
    ).toBe(charLimitMessage(500));
  });

  it("'{length}/{max}' 를 늘 보이고, 상태 클래스·data-state 를 단다", () => {
    expect(tpl).toContain('<span class="skx-charcount__num">{{ length }}/{{ max }}</span>');
    expect(tpl).toContain('class="skx-charcount"');
    expect(tpl).toContain(":class=\"{ 'skx-charcount--near': state === 'near', 'skx-charcount--limit': state === 'limit', 'skx-charcount--quiet': quiet }\"");
    expect(tpl).toContain(':data-state="state"');
  });

  it("한도 안내 칸은 늘 그려 둔 aria-live=polite — 한도일 때만 글이 들어간다", () => {
    expect(tpl).toContain('<span class="skx-charcount__msg" aria-live="polite">{{ state === "limit" ? limitMessage : "" }}</span>');
    expect(tpl).not.toMatch(/v-if="[^"]*limit/);
    // 글자 수 자체는 live 가 아니다(한 글자마다 읽히지 않게)
    expect(tpl).not.toMatch(/skx-charcount__num"[^>]*aria-live/);
  });

  it("props — length·max·near?, 상태 셈은 공용 순수 함수", () => {
    expect(js).toMatch(/length: number;/);
    expect(js).toMatch(/max: number;/);
    expect(js).toMatch(/near\?: number;/);
    expect(js).toContain("charCountState(props.length, props.max, props.near)");
    expect(js).toContain("charLimitMessage(props.max)");
  });
});

describe("SkxErrorPage — 전역 오류 화면 본문(preview)", () => {
  const tpl = template(pageVue);
  const js = script(pageVue);

  it("props — status·preview?(기본 false)", () => {
    expect(js).toMatch(/status: number;/);
    expect(js).toMatch(/preview\?: boolean;/);
    expect(js).toContain("{ preview: false }");
  });

  it("preview 면 버튼이 이동·새로고침을 하지 않는다", () => {
    expect(js).toMatch(/function goHome\(\): void \{\s*if \(props\.preview\) return;\s*clearError\(\{ redirect: "\/" \}\);\s*\}/);
    expect(js).toMatch(/function reload\(\): void \{\s*if \(props\.preview\) return;\s*window\.location\.reload\(\);\s*\}/);
  });

  it("preview 면 랜드마크·제목 요소를 쓰지 않고, 액자 높이를 채우는 갈래 클래스를 단다", () => {
    expect(tpl).toContain(":is=\"preview ? 'div' : 'main'\"");
    expect(js).toContain('props.preview ? "p" : "h1"');
    expect(tpl.match(/:title-tag="titleTag"/g)).toHaveLength(2);
    expect(tpl).toContain(":class=\"{ 'skx-error-page--preview': preview }\"");
    expect(tpl).toContain(':data-status="status"');
  });
});

describe("오류 화면 모음 페이지(/dev/error-states)", () => {
  const tpl = template(galleryVue);
  const js = script(galleryVue);
  const css = style(galleryVue);

  it("검색엔진에 싣지 않고 탭 제목을 단다", () => {
    expect(js).toMatch(/useHead\(\{\s*title: "오류 화면 모음 — SKOVIX",\s*meta: \[\{ name: "robots", content: "noindex,nofollow" \}\],\s*\}\)/);
  });

  it("메뉴(사이드바)에 잇지 않는다", () => {
    expect(tpl).not.toContain("<AppSidebar");
    for (const rel of ["components/AppSidebar.vue", "pages/index.vue", "pages/papers/index.vue", "app.vue"]) {
      expect(read(rel), rel).not.toContain("/dev/error-states");
    }
  });

  it("맨 위 안내 두 줄", () => {
    expect(tpl).toContain("이 페이지의 표시는 모두 실제 컴포넌트입니다.");
    expect(tpl).toMatch(/디자인은 <code>assets\/css\/style_skovix\.css<\/code> 의 <code>\[S\] 공통 오류·빈 상태<\/code> 구역 클래스에 입히면\s*실제 화면 전체에 반영됩니다\./);
  });

  it("테마 전환 — THEMES 목록을 돌며 useTheme 의 setTheme 으로 바꾼다", () => {
    expect(js).toContain('import { useTheme } from "~/composables/useTheme"');
    expect(js).toContain('import { THEMES, THEME_LABELS } from "~/utils/theme"');
    expect(js).toContain("const { theme, setTheme } = useTheme();");
    expect(tpl).toMatch(/v-for="name in THEMES"[\s\S]*?:aria-pressed="theme === name"[\s\S]*?@click="setTheme\(name\)"/);
  });

  it("표시는 모두 실제 컴포넌트 — 여섯 묶음이 각각 공통 컴포넌트를 쓴다", () => {
    expect(tpl).toContain('<SkxErrorPage :status="p.status" preview />');
    expect(js).toMatch(/status: 404,/);
    expect(js).toMatch(/status: 500,/);
    expect(tpl).toContain("<SkxErrorState");
    expect(tpl.match(/<SkxInlineError/g)).toHaveLength(3);
    expect(tpl).toContain("<SkxConnectionBanner");
    expect(tpl.match(/<SkxCharCount/g)).toHaveLength(2);
    expect(tpl.match(/<SkxConfirm\b/g)).toHaveLength(1);
    // 직접 쳐 보는 입력창 — maxlength 와 글자 수가 같은 한도
    expect(tpl).toMatch(/<textarea\s+:id="typeId"[\s\S]*?:maxlength="CHAR_MAX"[\s\S]*?:aria-describedby="countId"[\s\S]*?<\/textarea>\s*<SkxCharCount :id="countId" :length="typed\.length" :max="CHAR_MAX" :quiet="typedQuiet" \/>/);
  });

  it("복제 마크업 없음 — 공통 구역의 클래스를 페이지가 직접 그리지 않는다(슬롯 링크 .skx-state__action 만)", () => {
    const classes = [...tpl.matchAll(/\sclass="([^"]*)"/g)].flatMap((m) => m[1]!.split(/\s+/));
    const owned = classes.filter((c) => /^skx-(state|inline-error|conn|charcount|confirm|error-page|holo)(?:$|--|__)/.test(c));
    expect(owned).toEqual(["skx-state__action"]);
    expect(tpl).toContain('<a class="skx-state__action" :href="s.action.href" @click.prevent>');
    // ② 와 ③ 은 같은 틀(섹션 목록)을 돈다 — 상태 블록 마크업은 한 벌
    expect(tpl.match(/<SkxErrorState/g)).toHaveLength(1);
    expect(tpl).toMatch(/<section v-for="g in STATE_SECTIONS"/);
    // 이 페이지의 틀(.dev-*)은 공통 구역 클래스를 꾸미지 않는다
    expect(css).not.toMatch(/\.skx-/);
  });

  it("검색 입력 상자는 실제 클래스(.skx-search__box)로 모양을 맞춘다", () => {
    expect(tpl).toMatch(/<div class="skx-search__box">[\s\S]*?class="skx-search__input"[\s\S]*?class="skx-send"[\s\S]*?<\/div>\s*<\/div>\s*<SkxInlineError/);
  });

  it("문구는 규칙·상수에서 — 이유(ERROR_HINTS)를 화면에 적지 않는다", () => {
    expect(js).toContain("apiErrorMessage(err, \"\")");
    expect(js).toContain("errorKind(SAMPLE.network)");
    expect(js).toContain('researchErrorMessage(SAMPLE.notFound, "")');
    expect(js).toContain("AI_SUMMARY_FAILED");
    expect(js).toContain("CONNECTION_HINTS.reconnecting");
    expect(js).toContain("charLimitMessage(CHAR_MAX)");
    for (const hint of ["네트워크 연결을 확인해 주세요", "응답이 늦어", "요청이 몰려", "서버에 문제가", "자까지 입력할 수 있어요", "연결이 끊겨 다시 연결하는 중이에요", "화면이 최신 상태가 아닐 수"]) {
      expect(galleryVue, hint).not.toContain(hint);
    }
  });

  it("② 상태 블록 — 요구한 kind 와 재시도 중·compact 를 모두 보인다", () => {
    for (const id of ["error", "network", "timeout", "busy", "server", "searchDown", "notFound", "empty", "canceled", "retrying", "compact"]) {
      expect(js, id).toMatch(new RegExp(`id: "${id}",`));
    }
    expect(js).toMatch(/id: "retrying",[\s\S]*?busy: true,/);
    expect(js).toMatch(/id: "compact",[\s\S]*?compact: true,/);
    // 제목·설명은 실제 화면의 상수를 읽는다 — 화면 문구가 바뀌면 모음도 같이 바뀐다(하드코딩 금지)
    for (const ref of [
      "title: PAPER_STATE_TEXT.searchFailed,",
      "title: PAPER_STATE_TEXT.detailFailed,",
      "title: PAPER_STATE_TEXT.relatedFailed,",
      "title: WORK_SOURCES_FAILED,",
    ]) {
      expect(js, ref).toContain(ref);
    }
    expect(js).toMatch(/id: "empty",[\s\S]*?title: PAPER_STATE_TEXT\.searchEmpty,\s*message: PAPER_STATE_TEXT\.searchEmptyHint,/);
    for (const text of ["검색하지 못했어요", "논문 정보를 불러오지 못했어요", "관련 자료를 불러오지 못했어요", "원문 대목을 불러오지 못했어요", "검색 결과가 없어요", "다른 검색어로"]) {
      expect(js, text).not.toContain(`"${text}`);
    }
    // 상태 블록 제목을 글로 적지 않는다 — 글로 적은 title 은 섹션 제목뿐(실제 화면에 없는 빈 연구 안내는 지웠다)
    expect(js.match(/\n {4}title: "[^"]*"/g)).toEqual([
      '\n    title: "② 섹션 상태 블록 (SkxErrorState)"',
      '\n    title: "③ 딥리서치 상태 (후배 시안 변형)"',
      '\n    title: "⑧ 토스트 (.skx-toast)"',
      '\n    title: "⑨ 상태 배지·줄 상태 (공통 구역 밖)"',
      '\n    title: "⑩ 흐린 안내 글·카드 안 안내 (공통 구역 밖)"',
    ]);
    // 취소 kind·서버 code 문구(CODE_MESSAGES — 서버 detail 은 쓰지 않는다)
    expect(js).toMatch(/id: "canceled",[\s\S]*?kind: "canceled",/);
    expect(js).toMatch(/searchDown: \{ status: 503, data: \{ detail: "[^"]*", code: "search_unavailable" \} \}/);
    expect(js).toContain("message: reasonOf(SAMPLE.searchDown)");
  });

  it("③ 딥리서치 상태 — 시안 변형(실패·취소·찾을 수 없음)을 실제 동작에 맞춰, 항목마다 시안 대비 바꾼 점", () => {
    for (const id of ["researchFailed", "researchCanceled", "researchNotFound"]) {
      expect(js, id).toMatch(new RegExp(`id: "${id}",[\\s\\S]*?diff:`));
    }
    expect(js.match(/\n {4}diff:/g)).toHaveLength(3);
    expect(tpl).toContain('<template v-if="s.diff">');
    expect(tpl).toContain("<dt>시안 대비</dt>");
    // 제목·설명·버튼은 딥리서치 화면과 같은 상수·함수 — 실패의 설명·[다시 시도] 글도 같은 함수(보고서 작성 단계에서 멈춤)
    expect(js).toContain("title: RESEARCH_STATE_TEXT.failedTitle,");
    expect(js).toContain('message: researchFailedMessage("explored", true),');
    expect(js).toContain('retryLabel: researchRetryLabel("explored"),');
    expect(js).toContain("title: RESEARCH_STATE_TEXT.canceledTitle,");
    expect(js).toContain("message: RESEARCH_STATE_TEXT.canceledMessage,");
    expect(js).toContain("action: { label: RESEARCH_STATE_TEXT.restart, href: \"#\" },");
    // 실제 화면처럼 멈춘·취소한 연구는 카드 안의 compact 블록
    expect(js).toMatch(/id: "researchFailed",[\s\S]*?compact: true,[\s\S]*?id: "researchCanceled",[\s\S]*?compact: true,[\s\S]*?id: "researchNotFound",/);
    // 설명을 이 페이지에서 새로 짓지 않는다(실제 화면과 갈라지지 않게)
    expect(js).not.toMatch(/message: "[^"]*(근거는 남아 있어요|이어 갈 수 없어요)/);
    expect(js).toContain("message: RESEARCH_STATE_TEXT.notFoundMessage,");
    // 실제와 다른 시안 문구는 버튼·설명으로 쓰지 않는다(시안 대비 설명에서만 말한다)
    expect(js).not.toMatch(/label: "(문의하기|이어서 연구하기|새 연구 시작)"/);
    expect(js).not.toMatch(/(title|message): "[^"]*(접근 권한|중단된 지점부터|연구를 불러오지 못했어요|연구가 중단되었어요)/);
  });

  // 시안의 넷째 변형(결과 없음 — 아직 연구가 없음)은 실제 앱에 없다: 연구 기록이 없으면 사이드바 묶음이 [연구 시작하기] 버튼만 둔다
  it("③ 실제 앱에 없는 '결과 없음(아직 연구가 없음)'은 그리지 않고, 그 까닭을 ③ 설명에 적는다", () => {
    expect(js).not.toContain('id: "researchEmpty"');
    expect(galleryVue).not.toContain("아직 진행한 연구가 없어요");
    expect(js).not.toContain("START_RESEARCH_HREF");
    expect(js).toContain("시안의 넷째 변형(결과 없음 — 아직 연구가 없음)은 실제 앱에 없어 그리지 않았어요.");
    // 실제 앱 어디에도 그 빈 상태 문구가 없고, 사이드바는 [연구 시작하기] 버튼을 둔다
    const sidebar = read("components/AppSidebar.vue");
    expect(sidebar).not.toContain("진행한 연구가 없");
    expect(sidebar).toMatch(/v-else-if="!researchRows\.length"\s+type="button"\s+class="skx-history__start"/);
  });

  it("딥리서치 화면도 같은 상수를 쓴다 — 모음과 실제 화면의 문구가 함께 바뀐다", () => {
    const researchVue = read("pages/research/[id].vue");
    // 딥리서치 화면도 같은 상태 블록(SkxErrorState)에 같은 상수를 넘긴다
    expect(researchVue).toContain(':title="RESEARCH_NOT_FOUND" :message="RESEARCH_STATE_TEXT.notFoundMessage"');
    expect(researchVue).toContain('{{ RESEARCH_STATE_TEXT.backToSearch }}');
    expect(researchVue).toContain(':title="RESEARCH_STATE_TEXT.failedTitle"');
    expect(researchVue).toContain(':title="RESEARCH_STATE_TEXT.canceledTitle" :message="RESEARCH_STATE_TEXT.canceledMessage"');
    expect(researchVue).toContain("researchFailedMessage(view.value.stage, canRetry.value, view.value.lastError)");
    expect(researchVue.match(/\{\{ RESEARCH_STATE_TEXT\.restart \}\}/g)).toHaveLength(2);
    expect(researchVue).toContain("researchRetryLabel(view.value?.stage)");
    expect(researchVue).not.toMatch(/연구가 도중에 멈췄습니다|취소된 연구입니다|찾을 수 없는 연구입니다/);
  });

  // ── 문구 보기(논문 · 소장자료) — 디자이너가 소장자료 화면(소장자료 검색·도서 상세·상황별 추천)의 문구도 보게 ──

  /** STATE_SAMPLES 의 소스, 그 한 항목(stateSample({ … }) 한 덩이)과 그 소장자료 쪽(book: 뒤) */
  const stateSamplesSrc = js.match(/const STATE_SAMPLES: StateSample\[\] = \[([\s\S]*?)\n\];/)?.[1] ?? "";
  const sampleSrc = (id: string) => stateSamplesSrc.split("stateSample({").find((b) => b.includes(`id: "${id}",`)) ?? "";
  const bookSrc = (id: string) => sampleSrc(id).split("book: ")[1] ?? "";

  it("문구 보기 — ②·④ 머리에 테마 전환과 같은 설정 칸(보이는 이름표를 가리키는 묶음·aria-pressed 버튼), 처음은 논문, 둘이 같은 값", () => {
    expect(js).toContain('const AREAS = ["paper", "book"] as const;');
    expect(js).toContain('const AREA_LABELS: Record<Area, string> = { paper: "논문", book: "소장자료" };');
    expect(js).toContain('const area = ref<Area>("paper");');
    // 이름표(문구 보기)를 aria-labelledby 로 가리키는 묶음 안에 진짜 버튼 — 탭으로 오고 엔터·스페이스로 바꾸며, 고른 쪽은 aria-pressed
    const switches = [
      ...tpl.matchAll(
        /<p :?id="([^"]+)" class="dev-gallery__area-label">문구 보기<\/p>\s*<div class="skx-set__seg dev-gallery__seg" role="group" :?aria-labelledby="\1">\s*<button\s+v-for="name in AREAS"\s+:key="name"\s+type="button"\s+:class="\['skx-set__opt', area === name && 'is-active'\]"\s+:aria-pressed="area === name"\s+@click="area = name"\s*>\s*\{\{ AREA_LABELS\[name\] \}\}\s*<\/button>/g,
      ),
    ];
    expect(switches.map((m) => m[1])).toEqual(["`${g.id}-area`", "dev-sec-inline-area"]);
    expect(tpl).not.toMatch(/v-for="name in AREAS"[^>]*tabindex/);
    // ② 에만 — ③(딥리서치)에는 소장자료 쪽이 없다. ④ 는 머리에 직접 둔다
    expect(js.match(/areaSwitch: true,/g)).toHaveLength(1);
    expect(js).toMatch(/id: "dev-sec-state",[\s\S]*?samples: STATE_SAMPLES,\s*areaSwitch: true,/);
    expect(tpl).toContain('<div v-if="g.areaSwitch" class="dev-gallery__area">');
    expect(tpl.indexOf('id="dev-sec-inline"')).toBeLessThan(tpl.indexOf('id="dev-sec-inline-area"'));
    // 본보기는 고른 쪽으로 — 문구 보기가 없는 섹션은 늘 논문 쪽
    expect(tpl).toContain('<article v-for="s in shownStates(g)" :key="s.id" class="dev-item">');
    expect(js).toContain('const view: Area = g.areaSwitch ? area.value : "paper";');
    // 설정 칸의 모양은 공통 클래스(.skx-set__seg·.skx-set__opt) — 이 페이지는 폭만 준다
    expect(css).toMatch(/\.dev-gallery__seg \{\s*width: 10rem;\s*\}/);
  });

  it("② 소장자료 쪽 — 항목마다 그 상태에서 소장자료 화면이 보이는 제목·설명·버튼을 bookErrors 상수로", () => {
    expect(js).toContain(
      'import { BOOK_DETAIL_TEXT, BOOK_HISTORY_TEXT, BOOK_REASON_TEXT, BOOK_SEARCH_TEXT, SCENARIO_TEXT } from "~/utils/bookErrors";',
    );
    expect(js).toContain('const BOOK_HOME_ACTION = { label: BOOK_DETAIL_TEXT.home, href: "/" };');
    expect(js).toContain('const PICK_ANOTHER_ACTION = { label: SCENARIO_TEXT.pickAnother, href: "/recommend" };');
    // 일반 실패·서버 오류·찾을 수 없음 → 도서 상세(첫 화면 버튼), 네트워크·몰림 → 소장자료 검색, 시간 초과·좁은 칸 → 도서 상세의 관련 자료,
    // 서버가 알린 장애 → 상황별 추천, 결과 없음 → 소장자료 검색 0건
    const expected: Record<string, string[]> = {
      error: ['kind: "error",', "title: BOOK_DETAIL_TEXT.failedTitle,", "retry: true,", "action: BOOK_HOME_ACTION,"],
      network: ["kind: errorKind(SAMPLE.network),", "title: BOOK_SEARCH_TEXT.failedTitle,", "message: reasonOf(SAMPLE.network),", "retry: true,"],
      timeout: ["kind: errorKind(SAMPLE.timeout),", "title: BOOK_DETAIL_TEXT.relatedFailedTitle,", "message: reasonOf(SAMPLE.timeout),", "retry: true,"],
      busy: ["kind: errorKind(SAMPLE.busy),", "title: BOOK_SEARCH_TEXT.failedTitle,", "message: reasonOf(SAMPLE.busy),", "retry: true,"],
      server: [
        "kind: errorKind(SAMPLE.server),",
        "title: BOOK_DETAIL_TEXT.failedTitle,",
        "message: reasonOf(SAMPLE.server),",
        "retry: true,",
        "action: BOOK_HOME_ACTION,",
      ],
      searchDown: ["kind: errorKind(SAMPLE.searchDown),", "title: SCENARIO_TEXT.failedTitle,", "message: reasonOf(SAMPLE.searchDown),", "retry: true,"],
      notFound: [
        "kind: errorKind(SAMPLE.notFound),",
        "title: BOOK_DETAIL_TEXT.notFoundTitle,",
        "message: BOOK_DETAIL_TEXT.notFoundMessage,",
        "action: BOOK_HOME_ACTION,",
      ],
      empty: ['kind: "empty",', "title: BOOK_SEARCH_TEXT.emptyTitle,", "message: BOOK_SEARCH_TEXT.emptyMessage,"],
      compact: [
        "kind: errorKind(SAMPLE.network),",
        "title: BOOK_DETAIL_TEXT.relatedFailedTitle,",
        "message: reasonOf(SAMPLE.network),",
        "retry: true,",
        "compact: true,",
      ],
    };
    for (const [id, parts] of Object.entries(expected)) {
      const book = bookSrc(id);
      expect(book, id).toMatch(/^\{\n/);
      for (const part of parts) expect(book, `${id} — ${part}`).toContain(part);
    }
    // 이유가 없는 실패의 소장자료 쪽은 설명 줄 없이 제목과 버튼만(failureView), 찾을 수 없음·빈 결과는 다시 시도가 없다
    expect(bookSrc("error")).not.toContain("message:");
    expect(bookSrc("notFound")).not.toContain("retry");
    expect(bookSrc("empty")).not.toContain("retry");
    // 소장자료 화면에 없는 상태 — 취소(딥리서치뿐)·재시도 중(소장자료 화면은 다시 받는 동안 블록 대신 불러오는 중 표시)
    expect(bookSrc("canceled")).toMatch(/^\{ none: "[^"]*딥리서치[^"]*" \}/);
    expect(bookSrc("retrying")).toMatch(/^\{ none: "[^"]*불러오는 중[^"]*" \}/);
    // ② 의 모든 항목이 소장자료 쪽을 정했다 — 블록·없는 상태(none)·소장자료에만 있는 상태(only)
    const chunks = stateSamplesSrc.split("stateSample({").slice(1);
    expect(chunks).toHaveLength(13);
    for (const chunk of chunks) expect(chunk).toMatch(/\n {4}(book: \{|only: "book",)/);
    // 소장자료 쪽은 블록을 통째로 바꾼다 — 논문 쪽의 설명·버튼이 남지 않게 칸마다 옮긴다
    expect(js).toMatch(
      /kind: b\.kind,\s*title: b\.title,\s*message: b\.message,\s*retry: b\.retry,\s*retryLabel: b\.retryLabel,\s*busy: b\.busy,\s*compact: b\.compact,\s*action: b\.action,\s*texts: b\.texts,/,
    );
  });

  it("② 상황별 추천에만 있는 상태(없는 상황·추천할 도서 없음)는 소장자료로 볼 때만 — 문구·버튼은 상황별 추천 화면과 같은 상수", () => {
    expect(sampleSrc("scenarioUnknown")).toMatch(
      /only: "book",\s*kind: "notFound",\s*title: SCENARIO_TEXT\.unknownTitle,\s*message: SCENARIO_TEXT\.unknownMessage,\s*action: PICK_ANOTHER_ACTION,/,
    );
    expect(sampleSrc("scenarioEmpty")).toMatch(
      /only: "book",\s*kind: "empty",\s*title: SCENARIO_TEXT\.emptyTitle,\s*message: SCENARIO_TEXT\.emptyMessage,\s*action: PICK_ANOTHER_ACTION,/,
    );
    expect(js).toContain(".filter((s) => !s.only || s.only === view)");
    // 상황별 추천 화면도 같은 상수로 같은 두 상태를 그리고, 버튼은 상황 목록(/recommend)으로 간다
    const reco = read("pages/recommend/[id].vue");
    expect(reco).toContain('return { kind: "empty", title: SCENARIO_TEXT.emptyTitle, message: SCENARIO_TEXT.emptyMessage, retry: false };');
    expect(reco).toContain('return { kind: "notFound", title: SCENARIO_TEXT.unknownTitle, message: SCENARIO_TEXT.unknownMessage, retry: false };');
    expect(reco).toMatch(/to="\/recommend"\s+class="skx-state__action"\s*>\s*\{\{ SCENARIO_TEXT\.pickAnother \}\}/);
  });

  it("② 소장자료 쪽의 설명·버튼은 소장자료 화면의 규칙(failureView)이 실제로 만드는 것과 같다", () => {
    // 모음의 본보기 오류(SAMPLE)와 같은 값 — 설명 줄은 reasonOf(apiErrorMessage(err, "")), kind 는 errorKind
    const searchDown = { status: 503, data: { detail: "x", code: "search_unavailable" } };
    for (const err of [{ name: "FetchError" }, { status: 504 }, { status: 503 }, { status: 500 }, searchDown]) {
      expect(failureView(err, BOOK_SEARCH_TEXT.failedTitle)).toEqual({
        kind: errorKind(err),
        title: BOOK_SEARCH_TEXT.failedTitle,
        message: apiErrorMessage(err, ""),
        retry: true,
      });
    }
    // 이유가 없는 실패(409·403·그 밖)는 설명 줄 없이 — ② 일반 실패의 소장자료 쪽에 message 가 없는 까닭
    for (const status of [409, 403, 418]) {
      expect(failureView({ status }, BOOK_DETAIL_TEXT.failedTitle)).toMatchObject({ title: BOOK_DETAIL_TEXT.failedTitle, message: "", retry: true });
    }
    // 404 는 도서 상세가 넘기는 찾을 수 없음 — 다시 시도 없음
    const notFound = { kind: "notFound" as const, title: BOOK_DETAIL_TEXT.notFoundTitle, message: BOOK_DETAIL_TEXT.notFoundMessage };
    expect(failureView({ status: 404 }, BOOK_DETAIL_TEXT.failedTitle, notFound)).toEqual({ ...notFound, retry: false });
    // 화면마다 그 제목을 failureView 에 넘기고, 도서 상세는 불러오기 실패 블록에 늘 첫 화면 버튼(BOOK_DETAIL_TEXT.home → '/')
    expect(read("pages/index.vue")).toContain("searchFailure.value = failureView(e, BOOK_SEARCH_TEXT.failedTitle);");
    const detail = read("pages/books/[cnts_id].vue");
    expect(detail).toContain("pageFailure.value = failureView(e, BOOK_DETAIL_TEXT.failedTitle, {");
    expect(detail).toContain("relatedFailure.value = failureView(e, BOOK_DETAIL_TEXT.relatedFailedTitle)");
    expect(detail).toMatch(
      /<SkxErrorState\s+v-else-if="pageFailure"[\s\S]*?<button type="button" class="skx-state__action" @click="navigateTo\('\/'\)">\{\{ BOOK_DETAIL_TEXT\.home \}\}<\/button>\s*<\/SkxErrorState>/,
    );
    // 관련 자료 실패는 절 안의 좁은 칸 — ② 좁은 칸의 소장자료 쪽
    expect(detail).toMatch(/<SkxErrorState\s+v-else-if="relatedFailure"[^/]*?\scompact\s/);
    expect(read("pages/recommend/[id].vue")).toContain("loadFailure.value = failureView(e, SCENARIO_TEXT.failedTitle, scenarioEmpty());");
  });

  it("② 재시도 중은 소장자료 화면에 없다 — 소장자료 검색·도서 상세·상황별 추천은 다시 받는 동안 블록 대신 불러오는 중 표시를 그린다", () => {
    expect(read("pages/index.vue")).toMatch(/v-if="loading"[\s\S]*?<div v-else-if="searchFailure" class="skx-rframe">/);
    const detail = read("pages/books/[cnts_id].vue");
    expect(detail).toMatch(/<div v-if="pageLoading" class="dt-loading">[\s\S]*?<SkxErrorState\s+v-else-if="pageFailure"/);
    expect(detail).toMatch(/<p v-if="relatedLoading" class="dt-empty">[\s\S]*?<SkxErrorState\s+v-else-if="relatedFailure"/);
    expect(read("pages/recommend/[id].vue")).toMatch(/<SkxErrorState\s+v-if="loadFailure && !loading"/);
    for (const rel of ["pages/index.vue", "pages/books/[cnts_id].vue", "pages/recommend/[id].vue"]) {
      expect(read(rel), rel).not.toMatch(/<SkxErrorState[^>]*:busy=/);
    }
  });

  it("④ 소장자료 쪽 — 다시 시도 있음은 추천 이유(BOOK_REASON_TEXT·SCENARIO_TEXT.aiFailed), 기본은 소장자료 화면에 없는 상태, 재시도 중(사이드바)은 같다", () => {
    expect(js).toMatch(
      /retry: \{[\s\S]*?partial: AI_PARTIAL_TEXT,\s*texts: \[AI_SUMMARY_FAILED, RETRY_TEXT\],[\s\S]*?book: \{\s*partial: AI_PARTIAL_BOOK_TEXT,\s*texts: \[BOOK_REASON_TEXT\.partial, BOOK_REASON_TEXT\.failed, SCENARIO_TEXT\.aiFailed, RETRY_TEXT\],\s*\},/,
    );
    expect(js).toMatch(/basic: \{[\s\S]*?book: \{\s*none:/);
    expect(js.match(/busy: \{[\s\S]*?\n {2}\},/)?.[0]).not.toContain("book:");
    expect(tpl).toContain('<p class="skx-pai-section__text">{{ inlineShown.retry.partial }}</p>');
    expect(tpl).toContain(':message="inlineShown.retry.texts[0]!"');
    expect(tpl).toContain('<p v-if="inlineShown.basic.absent" class="dev-item__absent">{{ inlineShown.basic.absent }}</p>');
    expect(tpl).not.toContain("INLINE_SAMPLES.");
    expect(tpl).toContain('<p class="dev-gallery__note">{{ INLINE_NOTE }}</p>');
    // 실제 화면 — 받다 끊긴 추천 이유(SKOVIX 추천 1권)와 상황별 추천의 사유 생성 실패가 같은 줄 안내에 [다시 시도]
    expect(read("pages/index.vue")).toMatch(/<SkxInlineError\s+v-if="reasonStatus === 'interrupted'"\s+:message="BOOK_REASON_TEXT\.partial"\s+@retry=/);
    expect(read("pages/recommend/[id].vue")).toMatch(/<SkxInlineError\s+v-if="aiFailed && !loading"\s+:message="SCENARIO_TEXT\.aiFailed"\s+@retry=/);
  });

  it("소장자료 문구를 다시 적지 않는다 — bookErrors 의 글은 상수로만, 소장자료 화면에 없는 상태는 고정 안내 + 까닭", () => {
    const code = `${tpl}\n${js}`;
    for (const table of [BOOK_SEARCH_TEXT, BOOK_DETAIL_TEXT, SCENARIO_TEXT, BOOK_REASON_TEXT]) {
      // 두 문장 글은 문장마다 본다
      for (const line of Object.values(table).flatMap((text: string) => text.split("\n"))) expect(code, line).not.toContain(line);
    }
    expect(js).toContain('const BOOK_NONE_NOTE = "소장자료 화면에는 없는 상태예요.";');
    expect(js).toContain("const absentNote = (why: string): string => `${BOOK_NONE_NOTE}\\n${why}`;");
    expect(tpl).toContain('<p v-if="s.absent" class="dev-item__absent">{{ s.absent }}</p>');
    expect(css).toMatch(/\.dev-item__absent \{[^}]*white-space: pre-line;/);
  });

  it("⑤ [다시 연결] 흉내는 다시 연결하는 중 → 붙음(connected) → 다시 끊김으로 돈다", () => {
    expect(js).toMatch(/connState\[id\] = "reconnecting";[\s\S]*?connState\[id\] = "connected";[\s\S]*?connState\[id\] = "lost";/);
  });

  it("① 액자 — transform + overflow: hidden 으로 홀로그램(position: fixed)을 가두고, 16:10 화면을 액자 폭에 맞춰 줄인다", () => {
    expect(css).toMatch(/\.dev-frame \{[^}]*overflow: hidden;[^}]*transform: translateZ\(0\);/);
    expect(js).toContain("const SCREEN_W = 1024;");
    expect(js).toContain("const SCREEN_H = 640;");
    expect(js).toContain("aspectRatio: `${SCREEN_W} / ${SCREEN_H}`");
    expect(js).toContain("frameScale.value = width / SCREEN_W");
    expect(tpl).toMatch(/<a class="dev-gallery__link" :href="MISSING_PATH" target="_blank" rel="noopener">/);
    expect(js).toContain('const MISSING_PATH = "/dev/없는-주소";');
  });

  it("사실이 아닌 설명을 싣지 않는다 — 통합 뒤 실제 화면이 공통 컴포넌트를 쓴다", () => {
    // 재연결은 포기하지 않는다(백오프로 계속 다시 시도한다)
    expect(galleryVue).not.toContain("재연결을 거듭해도 붙지 못함");
    // 통합 전 설명 — 쓰는 화면이 전역 오류 화면뿐·딥리서치는 rs-card·실패 설명에 last_error 원문·백엔드 반영 전·입력창에 maxlength 없음
    for (const stale of ["전역 오류 화면(①)뿐", "차례로 이 컴포넌트로 옮길", "rs-card 로 그립니다", "그대로 붙인다", "백엔드 반영 뒤", "maxlength 가 없다", "대부분 아직"]) {
      expect(galleryVue, stale).not.toContain(stale);
    }
    // 실제로 그 컴포넌트를 쓰지 않는 자리(글자 수 없는 입력·상태 블록이 아닌 쓰기 실패)를 '생기는 곳'으로 들지 않는다
    for (const wrong of ["연구 계획 하위질문 고치기(300자)", "읽기 목록 메모(1000자)", "연구 작업대 저장", "모든 상태 블록", "모든 줄 안내"]) {
      expect(galleryVue, wrong).not.toContain(wrong);
    }
    expect(tpl).not.toContain("쓰이는 곳");
    expect(tpl).toContain("각 항목의 ‘생기는 곳’은 그 모양이 실제로 나오는 대표 화면입니다.");
    // 검색·관련 자료의 60초 제한은 호출부가 넘긴다(useApi 의 API_SEARCH_TIMEOUT_MS)
    expect(js).toContain("60초 제한 — API_SEARCH_TIMEOUT_MS");
    expect(read("composables/useApi.ts")).toContain("export const API_SEARCH_TIMEOUT_MS = 60_000;");
    expect(read("pages/papers/index.vue")).toContain("timeout: API_SEARCH_TIMEOUT_MS,");
  });

  it("DeepRead — 답을 받지 못한 말풍선은 '다시 시도 있음' 줄 안내, 질문 글자 수는 2000자", () => {
    expect(js).toMatch(/retry: \{[\s\S]*?"DeepRead 대화 — 답을 받지 못한 말풍선"[\s\S]*?\},\r?\n {2}busy:/);
    expect(js).toContain("`DeepRead 질문(${CHAT_MAX_CHARS}자)`");
    expect(CHAT_MAX_CHARS).toBe(2000);
    // 실제 DeepRead 화면이 그 컴포넌트를 쓴다
    const chat = read("components/BookChat.vue");
    expect(chat).toMatch(/<SkxInlineError\s+class="skx-chat-msg__failed"/);
    expect(chat).toContain(':max="CHAT_MAX_CHARS"');
  });

  it("④ 재시도 중 본보기는 사이드바가 실제로 보이는 목록 실패 문구(SIDEBAR_NOTICE.loadFailed)", () => {
    expect(js).toMatch(/busy: \{[\s\S]*?사이드바 기록[\s\S]*?texts: \[SIDEBAR_NOTICE\.loadFailed, RETRY_TEXT\],/);
    expect(js).not.toContain('"목록을 불러오지 못했어요"');
  });

  it("사이드바 빈 기록 안내 — ② 설명은 ⑩ 를 가리키고, ⑩ 가 사이드바 상수 글을 사이드바의 scoped 규칙으로 그린다", () => {
    expect(js).toContain("import { SIDEBAR_EMPTY, SIDEBAR_NOTICE } from \"~/utils/sidebarGroups\";");
    expect(js).toContain("사이드바의 빈 기록 안내(.skx-history__empty)는 사이드바 모양을 지키려 이 블록을 쓰지 않아요 — ⑩ 에 따로 그렸어요.");
    expect(js).not.toContain("디자인 대상 아님");
    // 모양은 AppSidebar.vue 의 scoped 규칙 — 그 컴포넌트의 scope 속성(__scopeId)을 같은 줄에 붙여 입힌다
    expect(tpl).toMatch(/<div v-else-if="s\.id === 'sidebarEmpty'" class="dev-side">\s*<p class="skx-history__empty" role="status" v-bind="SIDEBAR_SCOPE">\{\{ SIDEBAR_EMPTY \}\}<\/p>/);
    expect(js).toContain('import AppSidebar from "~/components/AppSidebar.vue";');
    expect(js).toContain("const scopeId = (AppSidebar as unknown as { __scopeId?: string }).__scopeId;");
    expect(js).toContain('return scopeId ? { [scopeId]: "" } : {};');
    // 실제 사이드바도 같은 상수·같은 클래스, 그 클래스의 모양은 사이드바 scoped 스타일에만 있다
    const sidebar = read("components/AppSidebar.vue");
    expect(sidebar).toContain("{{ SIDEBAR_EMPTY }}");
    expect(sidebar).toMatch(/<style scoped>[\s\S]*\.skx-history__empty \{/);
    expect(rawCss).not.toContain(".skx-history__empty");
    // 사이드바 바탕 — 사이드바 틀과 같은 면·글자 토큰(색 리터럴 없이)
    expect(css).toMatch(/\.dev-side \{[^}]*background: var\(--skx-frost-side-bg\);[^}]*--skx-gray-1: var\(--skx-side-gray-1\);/);
  });

  it("⑥ 글자 수 — quiet(평소엔 숨김) 본보기와 '검색창·질문 칸은 한도 가까이부터만' 설명, 직접 입력에서 quiet 를 켜 본다", () => {
    expect(tpl).toContain('<SkxCharCount :length="n.length" :max="CHAR_MAX" :quiet="n.quiet" />');
    expect(js).toContain('{ length: 120, name: "평소 — quiet (검색창·질문 칸 — 화면에 보이지 않음)", quiet: true },');
    expect(js).toContain('".skx-charcount--quiet"');
    expect(js).toMatch(/const COUNT_QUIET_NOTE =\s*"검색창·질문 칸\(DeepResearch·DeepRead 질문 포함\)은 모두 quiet 라 한도 가까이\(90%\)부터만 글자 수가 보여요\.\\n"/);
    // '평소' 모양은 지금 앱 어디에도 보이지 않는다 — 설명·이름·생기는 곳이 모두 그렇게 말한다
    expect(js).toContain("그래서 ‘평소’ 모양(숫자만)은 지금 앱 어디에도 보이지 않아요");
    expect(js).toContain('{ length: 120, name: "평소 (지금 앱에는 보이는 곳 없음)" },');
    expect(js).toContain('"지금 앱에는 없음 — 글자 수 칸이 모두 quiet 라 평소에는 숨어요(quiet 를 쓰지 않는 칸이 생기면 이 모양)"');
    // 그 말이 사실이다 — 앱의 글자 수 칸은 모두 quiet
    for (const rel of ["pages/index.vue", "pages/papers/index.vue", "components/detail/SearchBar.vue", "components/BookChat.vue"]) {
      const uses = read(rel).match(/<SkxCharCount\b[^>]*\/>/g) ?? [];
      expect(uses.length, rel).toBeGreaterThan(0);
      for (const use of uses) expect(use, rel).toMatch(/\squiet\s/);
    }
    expect(tpl).toContain('<p class="dev-gallery__note">{{ COUNT_QUIET_NOTE }}</p>');
    expect(tpl).toMatch(/<input v-model="typedQuiet" type="checkbox" \/>/);
    expect(js).toContain("const typedQuiet = ref(false);");
  });

  it("⑦ 확인 칸 — 실제 SkxConfirm 을 보고서 카드 위에, 문구는 화면과 같은 상수, 처음엔 펴 둔 채 초점을 옮기지 않는다", () => {
    expect(tpl).toContain('<h2 id="dev-sec-confirm" class="dev-gallery__h2">⑦ 확인 칸 (SkxConfirm)</h2>');
    // ⑥(글자 수) 다음, ⑧(토스트 — 공통 구역 밖) 앞 — 공통 구역 컴포넌트 묶음의 끝
    expect(tpl.indexOf('id="dev-sec-count"')).toBeLessThan(tpl.indexOf('id="dev-sec-confirm"'));
    expect(tpl.indexOf('id="dev-sec-confirm"')).toBeLessThan(tpl.indexOf('v-for="g in OUTSIDE_SECTIONS"'));
    expect(tpl).toMatch(/<div class="rs-card">\s*<SkxConfirm\s+v-if="confirmShown\[c\.id\]"/);
    expect(tpl).toContain(":initial-focus=\"confirmReopened[c.id] ? c.focus : 'none'\"");
    expect(tpl).toContain(':busy="c.busy || !!retrying[c.id]"');
    expect(js).toContain(
      "const confirmShown = reactive<Record<ConfirmSampleId, boolean>>({ remake: true, rewrite: true, remove: true, busy: true });",
    );
    // 문구는 실제 화면과 같은 상수 — 모음이 새로 적지 않는다
    expect(js).toContain('import { REMAKE_CONFIRM, REMAKE_CONFIRM_OK, REMAKE_REPORT } from "~/utils/workPhase";');
    for (const ref of [
      "message: REMAKE_CONFIRM,",
      "confirmLabel: REMAKE_CONFIRM_OK,",
      "message: REWRITE_CONFIRM,",
      "confirmLabel: REWRITE_CONFIRM_OK,",
      "message: REMOVE_CONFIRM,",
      "confirmLabel: REMOVE_CONFIRM_OK,",
    ]) {
      expect(js, ref).toContain(ref);
    }
    for (const text of ["이 문단을 지울까요", "다시 쓸까요", "계속할까요", "새 초안으로 바꿔요"]) {
      expect(galleryVue, text).not.toContain(text);
    }
    // 처음 초점 — 지우기는 [취소](컴포넌트 기본값), 골라 누른 다시 만들기·다시 쓰기는 확인 버튼(실제 화면과 같은 값)
    expect(js).toMatch(/id: "remake",[\s\S]*?focus: "confirm",/);
    expect(js).toMatch(/id: "rewrite",[\s\S]*?focus: "confirm",/);
    expect(js).toMatch(/id: "remove",[\s\S]*?focus: "cancel",/);
    expect(js).toMatch(/id: "busy",[\s\S]*?busy: true,/);
    expect(tpl).toContain("<dt>처음 초점</dt>");
    // 확인 버튼 흉내 — 잠깐 일하는 중이었다가 접힌다(요청은 보내지 않는다)
    expect(js).toMatch(/function simulateConfirm\(id: ConfirmSampleId\): void \{[\s\S]*?retrying\[id\] = true;[\s\S]*?confirmShown\[id\] = false;/);
  });

  it("도서·논문 404 문구를 모음이 글로 적지 않는다 — 그 문구는 각 화면 상수에만 있다", () => {
    for (const text of ["도서를 찾을 수 없어요", "논문을 찾을 수 없어요", "주소가 맞는지", "등록되지 않은"]) {
      expect(galleryVue, text).not.toContain(text);
    }
  });

  it("① 액자 속 배경 띠가 굵어 보이는 까닭(실제 창 크기 기준)을 캡션에 적는다", () => {
    expect(tpl).toContain("액자 속 배경 띠는 실제 창 크기(vmax·vh) 기준이라 줄인 액자에서는 굵게 보입니다");
  });

  it("⑧ 토스트 — 화면들과 같은 마크업을 늘 보이게(타이머·전환 없이), transform 을 준 칸이 position: fixed 를 가둔다", () => {
    expect(tpl).toMatch(
      /<div v-if="s\.id === 'toast'" class="dev-toast-stage">[\s\S]*?<div class="skx-toast" role="status" aria-live="polite">\{\{ BOOK_HISTORY_TEXT\.missing \}\}<\/div>/,
    );
    // 실제 화면은 같은 마크업을 v-if + Transition 으로 2.5초만 — 모음은 v-if·Transition 없이 늘 보인다
    expect(read("pages/index.vue")).toContain('<div v-if="toast" class="skx-toast" role="status" aria-live="polite">{{ toast }}</div>');
    expect(tpl).not.toContain('<Transition name="skx-toast">');
    expect(tpl).not.toContain('v-if="toast"');
    expect(css).toMatch(/\.dev-toast-stage \{[^}]*overflow: hidden;[^}]*transform: translateZ\(0\);/);
    // 모양은 공통 구역 밖(style_skovix.css 의 '── 토스트 ──') — 고정 위치·한 줄(nowrap)
    expect(rawCss).toMatch(/\.skx-toast \{[^}]*position: fixed;[^}]*white-space: nowrap;/);
    // 설명 — 토스트는 한 문장·한 줄
    expect(js).toContain('"토스트는 한 문장·한 줄이에요(white-space: nowrap — 줄을 바꾸지 않아요).\\n"');
    // 문구는 상수·규칙에서
    for (const ref of ["BOOK_HISTORY_TEXT.missing,", "BOOK_HISTORY_TEXT.unavailable,", "toastOf(pdfCheckProblem(404)),", "REPORT_EXPORT_FAILED_TOAST.docx,", "RESEARCH_TOAST_TEXT.linkCopyFailed,"]) {
      expect(js, ref).toContain(ref);
    }
  });

  it("⑨ 상태 배지·줄 상태 — 실제 클래스·실제 부품, 글은 화면과 같은 함수", () => {
    expect(tpl).toContain(
      '<span v-for="p in STOPPED_PHASES" :key="p" class="rs-status" :class="`rs-status--${p}`">{{ phaseLabel(p) }}</span>',
    );
    expect(js).toContain('const STOPPED_PHASES = ["failed", "canceled"] as const satisfies readonly ResearchPhase[];');
    expect(tpl).toContain('<span class="rs-badge rs-badge--failed">{{ subqStatusLabel(FAILED_SUBQ) }}</span>');
    expect(tpl).toContain(`<SynthProgressCard v-else-if="s.id === 'synthFailed'" :slots="DRAFT_SLOTS" :eta="DRAFT_ETA" />`);
    expect(tpl).toContain(`<ReportSkeleton v-else-if="s.id === 'slotStates'" :slots="PLAN_SLOTS" />`);
    expect(js).toContain("texts: [slotStateLabel(DRAFT_SLOTS[1]!, DRAFT_ETA)],");
    expect(js).toContain('texts: PLAN_SLOTS.filter((slot) => slot.state !== "collected").map((slot) => planSlotLabel(slot)),');
    // 실제 화면도 같은 클래스·같은 함수 — 연구 머리·탐색 경로
    expect(read("components/research/ResearchHeader.vue")).toContain(
      '<span class="rs-status" :class="`rs-status--${phase}`">{{ phaseLabel(phase) }}</span>',
    );
    expect(read("components/research/ProgressPanel.vue")).toContain(
      '<span class="rs-badge" :class="`rs-badge--${sq.status}`">{{ subqStatusLabel(sq) }}</span>',
    );
    // 모양은 research.css 에 따로 있다
    const researchCss = read("assets/css/research.css");
    for (const rule of [".rs-status--failed,", ".rs-badge--failed {", ".rs-synth__item.is-failed .rs-synth__icon {", ".rs-slot.is-failed .rs-slot__state {", ".rs-slot.is-empty {"]) {
      expect(researchCss, rule).toContain(rule);
    }
  });

  it("⑩ 흐린 안내 글·카드 안 안내 — 실제 클래스·실제 부품, 글은 화면과 같은 상수·함수", () => {
    expect(tpl).toContain('<p v-for="t in s.texts" :key="t" class="rs-muted">{{ t }}</p>');
    expect(js).toContain("texts: [moreLine(0), NO_LIMITS],");
    expect(tpl).toMatch(/<ReadingNextActions\s+class="wk-screen__next"\s+where="bottom"[\s\S]*?make-disabled\s+:hint="READING_HINT"/);
    expect(js).toContain("const READING_HINT = outlineHint({");
    expect(js).toContain('texts: present([READING_HINT, regenerateProblem([]), paragraphProblem("")]),');
    expect(tpl).toMatch(/<ReportView\s+v-else-if="s\.id === 'reportDraft'"\s+:report="DRAFT_REPORT"[\s\S]*?:draft="DRAFT_STOPPED"/);
    expect(js).toContain('const DRAFT_STOPPED = { slots: DRAFT_SLOTS, state: "interrupted" as DraftState, excluded: [] };');
    expect(js).toContain('texts: [draftBadge("interrupted").label, draftIntro(DRAFT_SLOTS, "interrupted"), INTROLESS],');
    expect(tpl).toMatch(/<TopicCard\s+v-else-if="s\.id === 'topicFailed' \|\| s\.id === 'topicChecks'"/);
    expect(js).toContain('texts: present([cardNote("failed"), cardNote("insufficient"), cardNote("blocked")]),');
    expect(js).toContain(
      "texts: present([keywordWarning(CHECKED_CARD), cardNumbersLine(CHECKED_CARD), reviewLine({ unmarked: 2, numbers: 1, first: null })]),",
    );
    expect(tpl).toContain('<ul class="wk-outline__problems">');
    expect(js).toContain('const OUTLINE_PROBLEMS = outlineProblems({ groups: [{ key: "g1", name: "", papers: [] }], question: "", method: "" }, true);');
    // 표지는 브라우저에서만 불러 실패(@error)를 놓치지 않는다
    expect(tpl).toMatch(/<ClientOnly>\s*<BookCover :book-id="MISSING_BOOK_ID" size="small" \/>\s*<\/ClientOnly>/);
    // 실제 부품이 같은 클래스·같은 함수로 그린다
    expect(read("components/work/TopicCard.vue")).toContain(`<p class="wk-topic__note" :aria-live="pending ? 'polite' : undefined">{{ note }}</p>`);
    expect(read("components/work/ReadingNextActions.vue")).toContain('<p v-if="hint" :id="hintId" class="rs-muted">{{ hint }}</p>');
    expect(read("components/research/ReportView.vue")).toContain('<p class="rs-report__intro">{{ intro }}</p>');
  });

  it("⑧~⑩ 항목마다 스타일 위치 — 고칠 파일·클래스와 '공통 구역을 따르지 않는다'는 말", () => {
    expect(tpl).toContain('<p class="dev-gallery__lead">{{ OUTSIDE_LEAD }}</p>');
    const ids = js.match(/type OutsideId =([\s\S]*?);/)?.[1]?.match(/"\w+"/g) ?? [];
    expect(ids).toHaveLength(13);
    for (const id of ids) {
      expect(js, id).toMatch(new RegExp(`id: ${id},[\\s\\S]*?styleAt: "[^"]+\\.(css|vue) 의 `));
    }
    expect(tpl).toContain("<dt>스타일 위치</dt>");
    expect(tpl).toContain("<dd>{{ styleLine(s.styleAt) }}</dd>");
    expect(js).toContain("return `${where} — ‘[S] 공통 오류·빈 상태’ 구역을 따르지 않는 따로 꾸미는 자리예요.`;");
    // 세 섹션이 같은 틀을 돈다
    expect(tpl).toMatch(/<section v-for="g in OUTSIDE_SECTIONS"/);
    for (const id of ["dev-sec-toast", "dev-sec-badge", "dev-sec-muted"]) {
      expect(js, id).toContain(`id: "${id}",`);
    }
  });

  it("⑧~⑩ 문구를 다시 적지 않는다 — 화면 문구는 상수·함수·부품이 만든 글만", () => {
    for (const text of [
      "없는 기록이라",
      "연결이 불안정해",
      "원문 파일이 없어요",
      "Word 문서를 만들지",
      "더 쓸 씨앗이",
      "자동 점검에서 보고할",
      "카드를 만들지 못했어요",
      "근거 부족 —",
      "제목에 「",
      "확인 필요 37%",
      "검토할 곳:",
      "묶음의 이름을 적어",
      "5편 이상이면",
      "다시 만들 수 있습니다",
      "빈 문단은",
      "완성되지 않은 초안",
      "멈춘 초안입니다",
      "도입 서술을 받지",
      "서술 받지 못함",
      "아직 검색 기록이 없어요",
    ]) {
      expect(galleryVue, text).not.toContain(text);
    }
  });

  it("⑪ 그리지 않은 것 — 글이 부품 안에만 있는 자리·표시 없는 상태·디자인 밖 화면", () => {
    expect(tpl).toContain('<h2 id="dev-sec-skip" class="dev-gallery__h2">⑪ 이 모음에 그리지 않은 것</h2>');
    expect(js).toMatch(/const SKIPPED: \{ name: string; lines: string\[\] \}\[\] = \[/);
    for (const hook of [".rs-subq__stopped", ".skx-aip__notice", ".skx-history-badge", ".dt-rc__why-text", "/admin/jobs", "/search-classic"]) {
      expect(js, hook).toContain(hook);
    }
    // [링크 복사] 실패는 이제 화면 안 토스트(⑧)다 — 브라우저 대화상자로 적지 않는다
    expect(js).not.toContain("window.prompt");
  });

  it("여러 문장 설명은 문장마다 줄을 바꾼다(pre-line)", () => {
    expect(css).toMatch(/\.dev-gallery__note \{[^}]*white-space: pre-line;/);
  });

  it("떠날 때 관찰자·타이머를 걷는다", () => {
    expect(js).toMatch(/onBeforeUnmount\(\(\) => \{\s*frameObserver\?\.disconnect\(\);\s*for \(const timer of timers\) clearTimeout\(timer\);/);
  });

  it("페이지 틀 스타일도 색은 토큰만", () => {
    expect(css.length).toBeGreaterThan(0);
    expect(colorLiterals(css)).toEqual([]);
  });
});

describe("CSS — 새 표시도 '[S] 공통 오류·빈 상태' 구역 안에", () => {
  const section = rawCss.match(/\/\* \[S\] 공통 오류·빈 상태[\s\S]*?\/\* \[E\] 공통 오류·빈 상태 \*\//)?.[0] ?? "";
  const code = section.replace(/\/\*[\s\S]*?\*\//g, "");

  it("띠·글자 수·오류 화면 preview 의 클래스를 꾸민다", () => {
    for (const cls of [
      ".skx-conn ",
      ".skx-conn__msg",
      ".skx-conn__retry",
      ".skx-conn--reconnecting",
      ".skx-conn--lost",
      ".skx-charcount ",
      ".skx-charcount__num",
      ".skx-charcount__msg",
      ".skx-charcount--near",
      ".skx-charcount--limit",
      ".skx-error-page--preview",
    ]) {
      expect(code, cls).toContain(cls);
    }
    // 구역 밖에서 같은 클래스를 다시 꾸미지 않는다
    const outside = rawCss.replace(section, "").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(outside).not.toMatch(/\.skx-(conn|charcount)\b/);
  });

  it("색은 토큰만 — 구역 전체에 색 리터럴이 없다", () => {
    expect(colorLiterals(section)).toEqual([]);
    // 연결하지 못함은 아이콘만 위험색(글자는 본문색), 글자 수 한도는 위험색이 아니라 포인트색
    expect(code).toMatch(/\.skx-conn--lost \.skx-conn__icon \{\s*color: var\(--skx-danger\);/);
    expect(code).not.toMatch(/\.skx-conn--lost \{/);
    expect(code).toMatch(/\.skx-conn \{[^}]*color: var\(--skx-ink\);/);
    expect(code).toMatch(/\.skx-charcount--limit \{[^}]*color: var\(--skx-primary\);/);
  });

  it("붙어 있음(connected)은 보이지 않게만 — display: none 이 아니라 알림 영역을 남긴다. 초점을 받은 띠는 키보드로 왔을 때만 테두리", () => {
    const connected = code.match(/\.skx-conn--connected \{([^}]*)\}/)?.[1] ?? "";
    expect(connected).toMatch(/position: absolute;/);
    expect(connected).toMatch(/clip-path: inset\(50%\);/);
    expect(connected).not.toMatch(/display: none|visibility: hidden/);
    expect(code).toMatch(/\.skx-conn:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
  });

  it("[다시 연결] 은 :focus-visible 테두리와 24px 누를 자리", () => {
    expect(code).toMatch(/\.skx-conn__retry:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
    expect(code).toMatch(/\.skx-conn__retry \{[^}]*min-height: 24px;/);
  });

  it("다시 연결하는 중의 깜빡임은 움직임 줄이기 설정에서 멈춘다", () => {
    expect(code).toMatch(/\.skx-conn--reconnecting \.skx-conn__icon::before \{[^}]*animation: skx-conn-pulse/);
    expect(code).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.skx-conn--reconnecting \.skx-conn__icon::before \{\s*animation: none;/);
  });

  it("글자 수 안내 칸(live 영역)을 display: none 으로 숨기지 않는다", () => {
    expect(code).not.toMatch(/\.skx-charcount__msg[^{]*\{[^}]*display: none/);
  });

  it("preview 오류 화면은 화면 높이 대신 액자 높이", () => {
    expect(code).toMatch(/\.skx-error-page--preview \{\s*min-height: 0;\s*height: 100%;/);
  });

  it("슬롯 버튼이 일하는 중(aria-disabled — 딥리서치 [같은 질문으로 다시 시작])도 [다시 시도] 재시도 중과 같은 모양", () => {
    expect(code).toMatch(/\.skx-state__retry\[aria-disabled="true"\],\s*\.skx-state__action\[aria-disabled="true"\] \{\s*opacity: 0\.55;\s*cursor: progress;/);
    expect(read("pages/research/[id].vue")).toMatch(/class="skx-state__action"\s+:aria-disabled="restarting \? 'true' : undefined"/);
  });

  it("낡은 주석이 지운 규칙을 가리키지 않는다 — DeepRead 말풍선의 .skx-retry 규칙은 없어졌다", () => {
    expect(rawCss).not.toContain(".skx-chat-msg--ai .skx-retry");
    expect(rawCss).not.toMatch(/실패 안내는 \.skx-retry/);
  });

  // 옛 [다시 시도] 글자 버튼(.skx-retry·.skx-pick__retry)은 모든 실패 안내가 SkxInlineError(.skx-inline-error__retry)로 옮겨 쓰는
  // 화면이 없다 — 규칙도, 그것을 가리키는 주석도 남기지 않는다
  it("쓰지 않는 옛 재시도 버튼 규칙(.skx-retry·.skx-pick__retry)이 없다", () => {
    expect(rawCss).not.toMatch(/\.skx-(?:pick__)?retry\b/);
  });

  it("슬롯 링크(.skx-state__action)는 지나간·마우스 올린 링크도 같은 색 — 공통 리셋 a:hover 를 이긴다(보조·주 버튼 둘 다)", () => {
    expect(code).toMatch(/\.skx-state__action:visited,\s*\.skx-state__action:hover \{\s*color: var\(--skx-ink\);/);
    expect(code).toMatch(
      /\.skx-state__actions > \.skx-state__action:first-child:visited,\s*\.skx-state__actions > \.skx-state__action:first-child:hover \{\s*color: var\(--skx-on-accent\);/,
    );
  });
});
