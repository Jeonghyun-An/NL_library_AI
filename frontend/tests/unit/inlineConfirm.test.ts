// frontend/tests/unit/inlineConfirm.test.ts
// 브라우저 확인 창(window.confirm) 대신 누른 버튼 곁에 펴는 확인 칸(SkxConfirm)(사용자 결정 — 오류·확인은 화면 안에서, 모달 금지).
// 연구 작업대의 네 자리(절 다시 쓰기·문단 지우기·보고서 단계와 참고문헌 단계의 [보고서 다시 만들기])가 이 컴포넌트를 쓴다.
// 문구 상수는 실제로 읽고, 컴포넌트·화면(.vue)은 Nuxt 를 띄우지 않고 소스 글을 검사한다(기존 관례 — 마운트 도구가 없다)
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { REMOVE_CONFIRM, REMOVE_CONFIRM_OK, REWRITE_CONFIRM, REWRITE_CONFIRM_OK } from "~/utils/proposalView";
import { REMAKE_CONFIRM, REMAKE_CONFIRM_OK } from "~/utils/workPhase";
import { rawCss } from "./helpers/themeCss";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8").replace(/\r\n/g, "\n");
/** <template> 부분만 — 머리 주석의 글에 속지 않게 */
const template = (src: string) => src.match(/<template>([\s\S]*)<\/template>/)?.[1] ?? "";
const script = (src: string) => src.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)?.[1] ?? "";
/** 주석(<!-- -->·/* *\/·//)을 지운 소스 — 주석에 적은 'window.confirm' 설명에 속지 않게 */
const code = (src: string) =>
  src
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .map((line) => line.replace(/(^|[^:"'`])\/\/.*$/, "$1"))
    .join("\n");

/** dir 아래의 .vue·.ts 파일(상대 경로) */
function sourceFiles(dir: string): string[] {
  const out: string[] = [];
  const walk = (abs: string) => {
    for (const name of readdirSync(abs)) {
      const full = join(abs, name);
      if (statSync(full).isDirectory()) walk(full);
      else if (/\.(vue|ts)$/.test(name)) out.push(relative(root, full).replace(/\\/g, "/"));
    }
  };
  walk(resolve(root, dir));
  return out;
}

const confirmVue = read("components/SkxConfirm.vue");

describe("브라우저 확인 창이 남지 않는다", () => {
  const files = [...sourceFiles("components"), ...sourceFiles("pages")];

  it("components·pages 를 훑는다", () => {
    expect(files).toContain("components/work/ProposalSection.vue");
    expect(files).toContain("pages/dev/error-states.vue");
  });

  it.each(files)("%s: window.confirm·전역 confirm( 호출이 없다", (file) => {
    const src = code(read(file));
    expect(src).not.toMatch(/\bwindow\.confirm\b/);
    expect(src).not.toMatch(/(?<![\w$.])confirm\s*\(/);
  });
});

describe("확인 칸 문구 — 해요체·문장마다 줄, 확인 버튼은 하는 일의 동사", () => {
  it("절 다시 쓰기·문단 지우기 문구는 예전 확인 창의 글 그대로 상수로 옮겼다", () => {
    expect(REWRITE_CONFIRM).toBe("이 절을 다시 쓰면 지금 문단(수락·고친·직접 쓴 문단 포함)을 새 초안으로 바꿔요.\n다시 쓸까요?");
    expect(REMOVE_CONFIRM).toBe("이 문단을 지울까요?");
    expect([REWRITE_CONFIRM_OK, REMOVE_CONFIRM_OK, REMAKE_CONFIRM_OK]).toEqual(["다시 쓰기", "지우기", "다시 만들기"]);
  });

  it.each([REWRITE_CONFIRM, REMOVE_CONFIRM, REMAKE_CONFIRM])("%s", (text) => {
    for (const line of text.split("\n")) {
      // 한 줄에 한 문장 — 문장 끝(.·?) 뒤에 다른 문장이 이어지지 않는다
      expect(line).toMatch(/[.?]$/);
      expect(line).not.toMatch(/[.?] \S/);
    }
    expect(text).not.toMatch(/습니다|입니다|[^주]세요/);
  });
});

describe("SkxConfirm — 누른 버튼 곁의 확인 칸", () => {
  const tpl = template(confirmVue);
  const js = script(confirmVue);

  it("role=alertdialog — 이름(aria-label)과 묻는 글(aria-describedby → .skx-confirm__msg)", () => {
    expect(tpl).toMatch(
      /<div\s+ref="root"\s+class="skx-confirm"\s+role="alertdialog"\s+:aria-label="label"\s+:aria-describedby="msgId"\s+@keydown\.esc\.stop="dismiss"\s*>/,
    );
    expect(tpl).toContain('<p :id="msgId" class="skx-confirm__msg">{{ message }}</p>');
    expect(js).toContain("const msgId = `skx-confirm-msg-${useId()}`;");
    // 모달이 아니다 — 흐름 안의 칸(aria-modal·Teleport 없음)
    expect(confirmVue).not.toMatch(/aria-modal|<Teleport/);
  });

  it("버튼 — [확인 동사] [취소], 디자인 훅 클래스", () => {
    expect(tpl).toMatch(/<div class="skx-confirm__actions">\s*<button\s+ref="okBtn"\s+type="button"\s+class="skx-confirm__ok"/);
    expect(tpl).toMatch(/class="skx-confirm__cancel"[\s\S]*?@click="dismiss"\s*>\s*\{\{ cancelLabel \}\}/);
    expect(tpl).toMatch(/class="skx-confirm__ok"[\s\S]*?@click="accept"\s*>\s*\{\{ confirmLabel \}\}/);
    expect(tpl.indexOf("skx-confirm__ok")).toBeLessThan(tpl.indexOf("skx-confirm__cancel"));
  });

  it("props — message·confirmLabel·label 은 받고, 취소 글 기본 '취소'·busy·처음 초점(기본 [취소])·돌아갈 곳", () => {
    expect(js).toMatch(/message: string;/);
    expect(js).toMatch(/confirmLabel: string;/);
    expect(js).toMatch(/cancelLabel\?: string;/);
    expect(js).toMatch(/label: string;/);
    expect(js).toMatch(/busy\?: boolean;/);
    expect(js).toMatch(/initialFocus\?: "confirm" \| "cancel" \| "none";/);
    expect(js).toMatch(/returnFocus\?: \(\) => HTMLElement \| null \| undefined;/);
    expect(js).toContain('{ cancelLabel: "취소", busy: false, initialFocus: "cancel" }');
    expect(js).toContain("const emit = defineEmits<{ confirm: []; cancel: [] }>();");
    // 기본값을 [취소]로 둔 까닭을 적어 둔다
    expect(js).toContain("덜 파괴적인 쪽에 처음 초점을 둔다");
  });

  it("일하는 중(busy) — 두 버튼 aria-disabled(초점 유지), 확인 버튼 aria-busy, 누름·Esc 무시", () => {
    expect(tpl.match(/:aria-disabled="busy \? 'true' : undefined"/g)).toHaveLength(2);
    expect(tpl.match(/:aria-busy="busy \? 'true' : undefined"/g)).toHaveLength(1);
    expect(tpl).not.toMatch(/:disabled=/);
    expect(js).toMatch(/function accept\(\): void \{\s*if \(!props\.busy\) emit\("confirm"\);\s*\}/);
    expect(js).toMatch(/function dismiss\(\): void \{\s*if \(!props\.busy\) emit\("cancel"\);\s*\}/);
  });

  it("펴지면 고른 버튼으로 초점을 옮기고('none' 이면 그대로), 펼 때 초점이 있던 곳을 쥔다", () => {
    expect(js).toMatch(
      /onMounted\(\(\) => \{\s*const active = document\.activeElement;\s*opener = active instanceof HTMLElement && active !== document\.body \? active : null;\s*if \(props\.initialFocus === "none"\) return;\s*\(props\.initialFocus === "confirm" \? okBtn : cancelBtn\)\.value\?\.focus\(\);\s*\}\);/,
    );
  });

  it("접힐 때 초점이 칸 안에 있었고 body 로 떨어졌을 때만 돌아갈 곳(returnFocus, 없으면 펼 때의 자리)으로 — 다른 곳으로 간 초점은 빼앗지 않는다", () => {
    expect(js).toMatch(
      /onBeforeUnmount\(\(\) => \{\s*hadFocus = !!root\.value\?\.contains\(document\.activeElement\);\s*back = props\.returnFocus;\s*\}\);/,
    );
    expect(js).toMatch(
      /onUnmounted\(\(\) => \{\s*if \(!hadFocus\) return;\s*void nextTick\(\(\) => \{\s*const active = document\.activeElement;\s*if \(active && active !== document\.body\) return;\s*const target = back \? back\(\) : opener\?\.isConnected \? opener : null;\s*target\?\.focus\(\);/,
    );
  });
});

describe("네 자리가 확인 칸을 쓴다 — 확인하면 예전에 확인 창이 '확인'을 돌려줬을 때의 일 그대로", () => {
  describe("보고서 절(ProposalSection) — 절 다시 쓰기·문단 지우기", () => {
    const src = read("components/work/ProposalSection.vue");
    const tpl = template(src);
    const js = script(src);

    it("확인 칸 세 자리 — 머리 아래·실패 줄 아래(절 다시 쓰기), 문단 버튼 줄 아래(지우기)", () => {
      expect(tpl.match(/<SkxConfirm\b/g)).toHaveLength(3);
      expect(tpl).toMatch(/<\/header>\s*(?:<!--[^]*?-->\s*)?<SkxConfirm\s+v-if="askWriteAt === 'head'"\s+v-bind="writeConfirm"/);
      expect(tpl).toMatch(/data-retry-line\s*\/>\s*<SkxConfirm\s+v-if="askWriteAt === 'retry'"\s+v-bind="writeConfirm"/);
      expect(tpl).toMatch(
        /<SkxConfirm\s+v-if="askRemovePid === p\.id"\s+:message="REMOVE_CONFIRM"\s+:confirm-label="REMOVE_CONFIRM_OK"\s+:label="`\$\{paraName\(pi\)\} 지우기 확인`"\s+:busy="asked"/,
      );
      // 지우기는 처음 초점을 [취소](컴포넌트 기본)로 둔다 — initial-focus 를 넘기지 않는다
      const remove = tpl.slice(tpl.indexOf('v-if="askRemovePid === p.id"'));
      expect(remove.slice(0, remove.indexOf("/>"))).not.toContain("initial-focus");
    });

    it("절 다시 쓰기 칸은 REWRITE_CONFIRM·[다시 쓰기]·확인 버튼에 처음 초점", () => {
      expect(js).toMatch(
        /const writeConfirm = computed\(\(\) => \(\{\s*message: REWRITE_CONFIRM,\s*confirmLabel: REWRITE_CONFIRM_OK,\s*label: `\$\{props\.label\} 다시 쓰기 확인`,\s*busy: asked\.value,\s*initialFocus: "confirm" as const,\s*\}\)\);/,
      );
    });

    it("수락·고친·직접 쓴 문단이 있을 때만 묻고, [다시 시도]도 같은 길 — 한 번에 하나(같은 버튼을 다시 누르면 접는다)", () => {
      expect(js).toMatch(
        /function onWrite\(at: "head" \| "retry"\): void \{\s*const kept = section\.value\?\.paragraphs\.some\(\(p\) => p\.state !== "proposed"\) \?\? false;\s*if \(kept\) \{\s*toggleAsk\(\{ kind: "write", at \}\);\s*return;\s*\}\s*emit\("write"\);\s*\}/,
      );
      expect(js).toMatch(/if \(section\.value\) \{\s*onWrite\("retry"\);/);
      expect(js).toMatch(/function remove\(pid: string\): void \{\s*if \(section\.value\) toggleAsk\(\{ kind: "remove", pid \}\);\s*\}/);
      expect(js).toContain("const ask = shallowRef<Ask | null>(null);");
      expect(js).toMatch(/ask\.value = ask\.value && askKey\(ask\.value\) === askKey\(next\) \? null : next;/);
      expect(tpl).toMatch(/data-write-open\s+@click="onWrite\('head'\)"/);
      expect(tpl).toMatch(/:aria-expanded="askRemovePid === p\.id"\s+:data-remove-for="p\.id"\s+@click="remove\(p\.id\)"/);
    });

    it("확인하면 절 쓰기(write)·문단을 뺀 절 저장(save) — 보낸 뒤에는 그 일이 끝날 때까지 busy", () => {
      expect(js).toMatch(/if \(a\.kind === "write"\) \{\s*asked\.value = true;\s*emit\("write"\);\s*return;\s*\}/);
      expect(js).toMatch(/asked\.value = true;\s*emit\("save", removeParagraph\(sec, a\.pid\)\);/);
    });

    it("묻던 일이 더는 맞지 않으면 걷는다 — 다른 일이 잠금·절을 쓰기 시작·문단이 없어짐·새 생성, 보낸 일이 끝남", () => {
      expect(js).toMatch(/watch\(locked, \(now\) => \{\s*if \(now && !asked\.value\) closeAsk\(\);\s*\}\);/);
      expect(js).toMatch(/watch\(status, \(now\) => \{\s*if \(now === "queued" \|\| now === "writing"\) closeAsk\(\);\s*\}\);/);
      expect(js).toMatch(/if \(pid && !paras\?\.some\(\(p\) => p\.id === pid\)\) closeAsk\(\);/);
      expect(js).toMatch(/\(\) => props\.busy,\s*\(now\) => \{\s*if \(!now && asked\.value\) closeAsk\(\);/);
      expect(js).toMatch(/\(\) => section\.value\?\.gen_id,[\s\S]*?pending = null;\s*closeAsk\(\);/);
    });

    it("접히면 초점은 연 버튼으로, 그 버튼이 사라졌거나 잠겼으면 절 제목으로", () => {
      expect(js).toMatch(
        /function askReturn\(selector: string\): HTMLElement \| null \{\s*const btn = rootEl\.value\?\.querySelector<HTMLButtonElement>\(selector\);\s*return btn && !btn\.disabled \? btn : document\.getElementById\(`wk-sec-title-\$\{props\.sectionKey\}`\);/,
      );
      expect(tpl).toContain(":return-focus=\"() => askReturn('[data-write-open]')\"");
      expect(tpl).toContain(":return-focus=\"() => askReturn('[data-retry-line] button')\"");
      expect(tpl).toContain(':return-focus="() => askReturn(removeSelector(p.id))"');
    });
  });

  describe("보고서 단계(ProposalStep) — [보고서 다시 만들기]", () => {
    const src = read("components/work/ProposalStep.vue");
    const tpl = template(src);
    const js = script(src);

    it("다시 맞춤 줄·대체 목차 줄(함께 보이지 않는다) 바로 아래 한 자리 — REMAKE_CONFIRM·[다시 만들기]·확인 버튼에 처음 초점", () => {
      expect(tpl.match(/<SkxConfirm\b/g)).toHaveLength(1);
      expect(tpl).toMatch(
        /<SkxInlineError\s+v-else-if="canRemake"\s+id="wk-proposal-fallback"[\s\S]*?@retry="makeOutline"\s*\/>\s*(?:<!--[^]*?-->\s*)?<SkxConfirm\s+v-if="remakeAsking"\s+:message="REMAKE_CONFIRM"\s+:confirm-label="REMAKE_CONFIRM_OK"\s+:label="`\$\{REMAKE_REPORT\} 확인`"\s+:busy="remakeSent"\s+initial-focus="confirm"\s+:return-focus="remakeReturn"\s+@confirm="confirmRemake"\s+@cancel="remakeAsking = false"/,
      );
      expect(tpl).toMatch(/id="wk-proposal-remake"[\s\S]*?:aria-expanded="remakeAsking"\s+@click="makeOutline"/);
    });

    it("목차가 있으면 칸을 펴고(다시 누르면 접는다), [다시 만들기]에서 만든다 — 목차가 없으면 바로 만든다", () => {
      expect(js).toMatch(/if \(proposal\.value\?\.outline\) \{\s*remakeAsking\.value = !remakeAsking\.value;\s*return;\s*\}\s*void runOutline\(\);/);
      expect(js).toMatch(
        /async function confirmRemake\(\): Promise<void> \{\s*if \(busy\.value \|\| remakeSent\.value\) return;\s*remakeSent\.value = true;\s*try \{\s*await runOutline\(\);\s*\} finally \{\s*remakeSent\.value = false;\s*remakeAsking\.value = false;\s*\}/,
      );
    });

    it("묻던 일이 더는 맞지 않으면 걷는다 — 보내기 전 다른 쓰기가 시작됨, 목차를 다시 만들기 시작함·다시 만들 까닭이 풀림", () => {
      expect(js).toMatch(/watch\(busy, \(now\) => \{\s*if \(now && !remakeSent\.value\) remakeAsking\.value = false;\s*\}\);/);
      expect(js).toMatch(/\(\) => canRemake\.value && !outlineGen\.value,\s*\(ok\) => \{\s*if \(!ok\) remakeAsking\.value = false;/);
      expect(js).toMatch(/return btn && !btn\.disabled \? btn : document\.getElementById\("wk-proposal-title"\);/);
    });
  });

  describe("참고문헌 단계(ReadingStep) — [보고서 다시 만들기](위·아래 두 묶음)", () => {
    const src = read("components/work/ReadingStep.vue");
    const tpl = template(src);
    const js = script(src);

    it("누른 묶음 바로 아래에 — 위·아래 중 한 곳에만(remakeAt)", () => {
      expect(tpl.match(/<SkxConfirm\b/g)).toHaveLength(2);
      expect(tpl).toMatch(
        /where="top"[^>]*\/>\s*<\/div>\s*(?:<!--[^]*?-->\s*)?<SkxConfirm v-if="reading && remakeAt === 'top'" v-bind="remakeConfirm" :return-focus="\(\) => remakeReturn\('top'\)" @confirm="confirmRemake" @cancel="remakeAt = null" \/>/,
      );
      expect(tpl).toMatch(
        /where="bottom"[^>]*\/>\s*<SkxConfirm v-if="remakeAt === 'bottom'" v-bind="remakeConfirm" :return-focus="\(\) => remakeReturn\('bottom'\)" @confirm="confirmRemake" @cancel="remakeAt = null" \/>/,
      );
      expect(js).toContain("const remakeAt = ref<NextActionsWhere | null>(null);");
      expect(js).toMatch(/if \(again\) \{\s*remakeAt\.value = remakeAt\.value === where \? null : where;\s*return;\s*\}\s*await runOutline\(\);/);
    });

    it("REMAKE_CONFIRM·[다시 만들기]·확인 버튼에 처음 초점, 만드는 동안 busy — 끝나면 걷힌다", () => {
      expect(js).toMatch(
        /const remakeConfirm = computed\(\(\) => \(\{\s*message: REMAKE_CONFIRM,\s*confirmLabel: REMAKE_CONFIRM_OK,\s*label: `\$\{REMAKE_REPORT\} 확인`,\s*busy: busy\.value,\s*initialFocus: "confirm" as const,\s*\}\)\);/,
      );
      expect(js).toMatch(
        /async function confirmRemake\(\): Promise<void> \{\s*if \(busy\.value \|\| readOnly\.value \|\| !canOutline\.value\) return;\s*await runOutline\(\);\s*remakeAt\.value = null;\s*\}/,
      );
    });

    it("[보고서 다시 만들기]가 사라지거나 꺼지면 걷고(만드는 중은 그대로), 접히면 그 묶음의 버튼·없으면 단계 제목으로", () => {
      expect(js).toMatch(/watch\(remakeAllowed, \(ok\) => \{\s*if \(!ok && !busy\.value\) remakeAt\.value = null;\s*\}\);/);
      expect(js).toMatch(
        /function remakeReturn\(where: NextActionsWhere\): HTMLElement \| null \{\s*const btn = document\.getElementById\(remakeButtonId\(where\)\) as HTMLButtonElement \| null;\s*return btn && !btn\.disabled \? btn : document\.getElementById\("wk-reading-title"\);/,
      );
    });
  });
});

describe("CSS — 확인 칸도 '[S] 공통 오류·빈 상태' 구역 안에", () => {
  const section = rawCss.match(/\/\* \[S\] 공통 오류·빈 상태[\s\S]*?\/\* \[E\] 공통 오류·빈 상태 \*\//)?.[0] ?? "";
  const body = section.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\r\n/g, "\n");
  /** 그 선택자 하나만 단 규칙의 본문(여러 선택자를 묶은 규칙은 건너뛴다) */
  const rule = (selector: string) => {
    const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return body.match(new RegExp(`(?:^|\\})\\s*${esc} \\{([^}]*)\\}`))?.[1] ?? null;
  };

  it("구역 머리 주석이 SkxConfirm 을 든다", () => {
    expect(section).toMatch(/^\/\* \[S\] 공통 오류·빈 상태 — [^*]*SkxConfirm\(누른 버튼 곁의 확인 칸\)/);
  });

  it("디자인 훅 — .skx-confirm·__msg·__actions·__ok·__cancel 이 구역 안에만 있다", () => {
    for (const cls of [".skx-confirm", ".skx-confirm__msg", ".skx-confirm__actions", ".skx-confirm__ok", ".skx-confirm__cancel"]) {
      expect(rule(cls), cls).not.toBeNull();
    }
    const outside = rawCss.replace(section, "").replace(/\/\*[\s\S]*?\*\//g, "");
    expect(outside).not.toMatch(/\.skx-confirm\b/);
  });

  it("묻는 글은 본문색·문장마다 줄(pre-line) — 빨갛게 칠하지 않는다", () => {
    expect(rule(".skx-confirm__msg")).toMatch(/color: var\(--skx-ink\);/);
    expect(rule(".skx-confirm__msg")).toMatch(/white-space: pre-line;/);
    expect(rule(".skx-confirm")).toMatch(/color: var\(--skx-ink\);/);
    const confirmRules = body.match(/\.skx-confirm[^{]*\{[^}]*\}/g) ?? [];
    expect(confirmRules.length).toBeGreaterThan(5);
    for (const r of confirmRules) expect(r).not.toContain("--skx-danger");
  });

  it("확인은 포인트색 채움(상태 블록 주 버튼과 같은 토큰), 취소는 선만 — 일하는 중은 aria-disabled 로 흐리게, 키보드 초점 테두리", () => {
    expect(rule(".skx-confirm__ok")).toMatch(/color: var\(--skx-on-accent\);\s*background: var\(--skx-primary\);/);
    expect(rule(".skx-confirm__cancel")).toMatch(/background: none;\s*border: 1px solid var\(--skx-line\);/);
    expect(body).toMatch(
      /\.skx-confirm__ok\[aria-disabled="true"\],\s*\.skx-confirm__cancel\[aria-disabled="true"\] \{\s*opacity: 0\.55;\s*cursor: progress;/,
    );
    expect(body).toMatch(/\.skx-confirm__ok:focus-visible,\s*\.skx-confirm__cancel:focus-visible \{\s*outline: 2px solid var\(--skx-accent\);/);
  });
});
