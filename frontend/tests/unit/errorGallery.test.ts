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
} from "~/utils/apiErrors";
import { rawCss } from "./helpers/themeCss";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");

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
      lost: "연결하지 못했어요. 화면이 최신 상태가 아닐 수 있어요",
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
    expect(tpl).toContain(":class=\"{ 'skx-charcount--near': state === 'near', 'skx-charcount--limit': state === 'limit' }\"");
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

  it("표시는 모두 실제 컴포넌트 — 다섯 묶음이 각각 공통 컴포넌트를 쓴다", () => {
    expect(tpl).toContain('<SkxErrorPage :status="p.status" preview />');
    expect(js).toMatch(/status: 404,/);
    expect(js).toMatch(/status: 500,/);
    expect(tpl).toContain("<SkxErrorState");
    expect(tpl.match(/<SkxInlineError/g)).toHaveLength(3);
    expect(tpl).toContain("<SkxConnectionBanner");
    expect(tpl.match(/<SkxCharCount/g)).toHaveLength(2);
    // 직접 쳐 보는 입력창 — maxlength 와 글자 수가 같은 한도
    expect(tpl).toMatch(/<textarea\s+:id="typeId"[\s\S]*?:maxlength="CHAR_MAX"[\s\S]*?:aria-describedby="countId"[\s\S]*?<\/textarea>\s*<SkxCharCount :id="countId" :length="typed\.length" :max="CHAR_MAX" \/>/);
  });

  it("복제 마크업 없음 — 공통 구역의 클래스를 페이지가 직접 그리지 않는다(슬롯 링크 .skx-state__action 만)", () => {
    const classes = [...tpl.matchAll(/\sclass="([^"]*)"/g)].flatMap((m) => m[1]!.split(/\s+/));
    const owned = classes.filter((c) => /^skx-(state|inline-error|conn|charcount|error-page|holo)(?:$|--|__)/.test(c));
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
    for (const title of ["검색하지 못했어요", "논문 정보를 불러오지 못했어요", "검색 결과가 없어요"]) {
      expect(js, title).toContain(`title: "${title}"`);
    }
    // 취소 kind·서버 code 문구(CODE_MESSAGES — 서버 detail 은 쓰지 않는다)
    expect(js).toMatch(/id: "canceled",[\s\S]*?kind: "canceled",/);
    expect(js).toMatch(/searchDown: \{ status: 503, data: \{ detail: "[^"]*", code: "search_unavailable" \} \}/);
    expect(js).toContain("message: reasonOf(SAMPLE.searchDown)");
  });

  it("③ 딥리서치 상태 — 시안 네 변형(실패·취소·찾을 수 없음·결과 없음)을 실제 동작에 맞춰, 항목마다 시안 대비 바꾼 점", () => {
    for (const id of ["researchFailed", "researchCanceled", "researchNotFound", "researchEmpty"]) {
      expect(js, id).toMatch(new RegExp(`id: "${id}",[\\s\\S]*?diff:`));
    }
    expect(js.match(/\n {4}diff:/g)).toHaveLength(4);
    expect(tpl).toContain('<template v-if="s.diff">');
    expect(tpl).toContain("<dt>시안 대비</dt>");
    // 제목·버튼은 딥리서치 화면과 같은 상수 — 실패의 [다시 시도] 글도 같은 함수(보고서 작성 단계에서 멈춤)
    expect(js).toContain("title: RESEARCH_STATE_TEXT.failedTitle,");
    expect(js).toContain('retryLabel: researchRetryLabel("explored"),');
    expect(js).toContain("title: RESEARCH_STATE_TEXT.canceledTitle,");
    expect(js).toContain("action: { label: RESEARCH_STATE_TEXT.restart, href: \"#\" },");
    expect(js).toContain("message: RESEARCH_STATE_TEXT.notFoundMessage,");
    expect(js).toContain("action: { label: \"연구 시작하기\", href: START_RESEARCH_HREF },");
    expect(js).toContain("deepResearchStartRoute()");
    // 실제와 다른 시안 문구는 버튼·설명으로 쓰지 않는다(시안 대비 설명에서만 말한다)
    expect(js).not.toMatch(/label: "(문의하기|이어서 연구하기|새 연구 시작)"/);
    expect(js).not.toMatch(/(title|message): "[^"]*(접근 권한|중단된 지점부터|연구를 불러오지 못했어요|연구가 중단되었어요)/);
  });

  it("딥리서치 화면도 같은 상수를 쓴다 — 모음과 실제 화면의 문구가 함께 바뀐다", () => {
    const researchVue = read("pages/research/[id].vue");
    expect(researchVue).toContain("{{ RESEARCH_NOT_FOUND }}");
    expect(researchVue).toContain("{{ RESEARCH_STATE_TEXT.notFoundMessage }}");
    expect(researchVue).toContain("{{ RESEARCH_STATE_TEXT.failedTitle }}");
    expect(researchVue).toContain("{{ RESEARCH_STATE_TEXT.canceledTitle }}");
    expect(researchVue.match(/\{\{ RESEARCH_STATE_TEXT\.restart \}\}/g)).toHaveLength(2);
    expect(researchVue).toContain("researchRetryLabel(view.value?.stage)");
    expect(researchVue).not.toMatch(/연구가 도중에 멈췄습니다|취소된 연구입니다|찾을 수 없는 연구입니다/);
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

  it("아직 사실이 아닌 설명을 싣지 않는다 — 검색 60초 제한(호출부가 아직 넘기지 않는다)·재연결 포기(백오프로 계속 다시 시도한다)", () => {
    expect(galleryVue).not.toContain("60초 제한");
    expect(galleryVue).not.toContain("재연결을 거듭해도 붙지 못함");
    // 대부분의 화면은 아직 이 컴포넌트를 쓰지 않는다 — '쓰이는 곳' 이 아니라 같은 상황이 '생기는 곳'
    expect(tpl).not.toContain("쓰이는 곳");
    expect(tpl).toContain("지금 이 컴포넌트를 실제로 쓰는 화면은 전역 오류 화면(①)뿐입니다.");
  });

  it("① 액자 속 배경 띠가 굵어 보이는 까닭(실제 창 크기 기준)을 캡션에 적는다", () => {
    expect(tpl).toContain("액자 속 배경 띠는 실제 창 크기(vmax·vh) 기준이라 줄인 액자에서는 굵게 보입니다");
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

  it("슬롯 링크(.skx-state__action)는 지나간·마우스 올린 링크도 같은 색 — 공통 리셋 a:hover 를 이긴다(보조·주 버튼 둘 다)", () => {
    expect(code).toMatch(/\.skx-state__action:visited,\s*\.skx-state__action:hover \{\s*color: var\(--skx-ink\);/);
    expect(code).toMatch(
      /\.skx-state__actions > \.skx-state__action:first-child:visited,\s*\.skx-state__actions > \.skx-state__action:first-child:hover \{\s*color: var\(--skx-on-accent\);/,
    );
  });
});
