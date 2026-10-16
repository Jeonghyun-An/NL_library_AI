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

  it("문구 — 다시 연결하는 중 / 연결하지 못함 + [다시 연결]", () => {
    expect(CONNECTION_HINTS).toEqual({
      reconnecting: "연결이 끊겨 다시 연결하는 중입니다…",
      lost: "연결하지 못했습니다. 화면이 최신 상태가 아닐 수 있습니다",
    });
    expect(CONNECTION_RETRY_LABEL).toBe("다시 연결");
    expect(tpl).toContain('<span class="skx-conn__msg">{{ CONNECTION_HINTS[state] }}</span>');
    expect(tpl).toContain("{{ CONNECTION_RETRY_LABEL }}");
  });

  it("디자인 훅 — .skx-conn·.skx-conn--{state}·data-state", () => {
    expect(tpl).toContain('class="skx-conn"');
    expect(tpl).toContain(':class="`skx-conn--${state}`"');
    expect(tpl).toContain(':data-state="state"');
  });

  it("다시 연결하는 중은 status(조용히), 연결하지 못함은 alert(바로 읽음)", () => {
    expect(tpl).toContain(":role=\"state === 'lost' ? 'alert' : 'status'\"");
  });

  it("[다시 연결] 은 lost 이고 부모가 @retry 를 달았을 때만", () => {
    expect(js).toMatch(/state: ConnectionState;/);
    expect(js).toMatch(/onRetry\?: \(\) => void;/);
    expect(js).toContain('import { CONNECTION_HINTS, CONNECTION_RETRY_LABEL, type ConnectionState } from "~/utils/apiErrors"');
    expect(tpl).toMatch(/<button v-if="state === 'lost' && onRetry" type="button" class="skx-conn__retry" @click="onRetry\?\.\(\)">/);
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
    expect(charLimitMessage(500)).toBe("500자까지 입력할 수 있습니다");
    expect(charLimitMessage(500)).toBe(VALIDATION_HINTS.tooLong.replace("{n}", "500"));
    expect(
      apiErrorMessage({ status: 422, data: { detail: [{ type: "string_too_long", ctx: { max_length: 500 } }] } }, "검색하지 못했습니다"),
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
    expect(tpl).toContain('<a class="skx-state__action" :href="s.back.href" @click.prevent>');
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
    for (const hint of ["네트워크 연결을 확인하세요", "응답이 늦어", "요청이 몰려", "서버에 문제가", "자까지 입력할 수 있습니다", "연결이 끊겨 다시 연결하는 중입니다", "화면이 최신 상태가 아닐 수"]) {
      expect(galleryVue, hint).not.toContain(hint);
    }
  });

  it("② 상태 블록 — 요구한 kind 와 재시도 중·compact 를 모두 보인다", () => {
    for (const id of ["error", "network", "timeout", "busy", "server", "notFound", "empty", "retrying", "compact"]) {
      expect(js, id).toMatch(new RegExp(`id: "${id}",`));
    }
    expect(js).toMatch(/id: "retrying",[\s\S]*?busy: true,/);
    expect(js).toMatch(/id: "compact",[\s\S]*?compact: true,/);
    for (const title of ["검색하지 못했습니다", "논문 정보를 불러오지 못했습니다", "검색 결과가 없습니다"]) {
      expect(js, title).toContain(`title: "${title}"`);
    }
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
    expect(code).toMatch(/\.skx-conn--lost \{[^}]*color: var\(--skx-danger\);/);
    expect(code).toMatch(/\.skx-charcount--limit \{[^}]*color: var\(--skx-danger\);/);
  });

  it("[다시 연결] 은 :focus-visible 테두리와 24px 누를 자리", () => {
    expect(code).toMatch(/\.skx-conn__retry:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
    expect(code).toMatch(/\.skx-conn__retry \{[^}]*min-height: 24px;/);
  });

  it("다시 연결하는 중의 깜빡임은 움직임 줄이기 설정에서 멈춘다", () => {
    expect(code).toMatch(/\.skx-conn--reconnecting \.skx-conn__msg::before \{\s*animation: skx-conn-pulse/);
    expect(code).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.skx-conn--reconnecting \.skx-conn__msg::before \{\s*animation: none;/);
  });

  it("글자 수 안내 칸(live 영역)을 display: none 으로 숨기지 않는다", () => {
    expect(code).not.toMatch(/\.skx-charcount__msg[^{]*\{[^}]*display: none/);
  });

  it("preview 오류 화면은 화면 높이 대신 액자 높이", () => {
    expect(code).toMatch(/\.skx-error-page--preview \{\s*min-height: 0;\s*height: 100%;/);
  });

  it("슬롯 링크(.skx-state__action)는 지나간·마우스 올린 링크도 같은 색 — 공통 리셋 a:hover 를 이긴다", () => {
    expect(code).toMatch(/\.skx-state__action:visited,\s*\.skx-state__action:hover \{\s*color: var\(--skx-primary\);/);
  });
});
