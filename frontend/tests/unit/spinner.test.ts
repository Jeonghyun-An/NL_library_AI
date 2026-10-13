// frontend/tests/unit/spinner.test.ts
// 로딩 스피너 교체(2026-10-13 사용자 결정) — 스스로 도는 160px GIF(깔끔·뚱뚱 입체 두 종류)와 정지 PNG, 상수 한 곳, CSS 회전 없음.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SPINNER_DONE_SRC, SPINNER_SRC, SPINNER_VARIANTS } from "~/utils/brand";

const root = resolve(__dirname, "../..");
const read = (rel: string) => readFileSync(resolve(root, rel), "utf-8");
const publicFile = (src: string) => resolve(root, "public", `.${src}`);

/** GIF 를 블록 단위로 읽어 크기·프레임 수·프레임 시간·무한 반복·투명 여부를 돌려준다 */
function readGif(path: string) {
  const b = readFileSync(path);
  expect(b.subarray(0, 6).toString("ascii")).toMatch(/^GIF8[79]a$/);
  const width = b.readUInt16LE(6);
  const height = b.readUInt16LE(8);
  let p = 13;
  if (b[10]! & 0x80) p += 3 * (1 << ((b[10]! & 7) + 1));
  let frames = 0;
  let infinite = false;
  let transparent = false;
  const delays: number[] = [];
  while (p < b.length) {
    const sep = b[p]!;
    if (sep === 0x3b) break;
    if (sep === 0x21) {
      const label = b[p + 1]!;
      if (label === 0xf9) {
        transparent ||= (b[p + 3]! & 1) === 1;
        delays.push(b.readUInt16LE(p + 4) * 10);
      }
      if (label === 0xff && b.subarray(p + 3, p + 14).toString("ascii") === "NETSCAPE2.0") {
        infinite = b.readUInt16LE(p + 16) === 0;
      }
      p += 2;
      while (b[p] !== 0) p += b[p]! + 1;
      p += 1;
    } else if (sep === 0x2c) {
      frames += 1;
      const flags = b[p + 9]!;
      p += 10;
      if (flags & 0x80) p += 3 * (1 << ((flags & 7) + 1));
      p += 1; // LZW 최소 코드 크기
      while (b[p] !== 0) p += b[p]! + 1;
      p += 1;
    } else {
      throw new Error(`알 수 없는 GIF 블록 0x${sep.toString(16)}`);
    }
  }
  return { width, height, frames, delays, infinite, transparent };
}

function pngSize(path: string): [number, number] {
  const b = readFileSync(path);
  expect(b.subarray(1, 4).toString("ascii")).toBe("PNG");
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}

describe("스피너 상수(utils/brand.ts)", () => {
  it("기본은 깔끔 축소본이고, 변형은 깔끔·뚱뚱 입체 두 가지다", () => {
    expect(SPINNER_SRC).toBe("/skovix-spinner-clean-160.gif");
    expect(SPINNER_SRC).toBe(SPINNER_VARIANTS.clean);
    expect(Object.keys(SPINNER_VARIANTS).sort()).toEqual(["bold", "clean"]);
    expect(SPINNER_VARIANTS.bold).toBe("/skovix-spinner-bold-160.gif");
    expect(SPINNER_DONE_SRC).toBe("/skovix-spinner-front-160.png");
  });

  it("변형 파일과 정지 그림이 public 에 실제로 있다", () => {
    for (const src of [...Object.values(SPINNER_VARIANTS), SPINNER_DONE_SRC]) {
      expect(existsSync(publicFile(src)), `${src} 가 public 에 없다`).toBe(true);
    }
  });
});

describe("축소본 파일 — 160×160·애니메이션 유지·투명 배경·용량", () => {
  const specs = [
    { name: "깔끔", src: SPINNER_VARIANTS.clean, frames: 96, totalMs: 4800 },
    { name: "뚱뚱 입체", src: SPINNER_VARIANTS.bold, frames: 80, totalMs: 3600 },
  ];

  it.each(specs)("$name: 160×160 이고 원본 프레임 수·전체 시간을 유지하며 무한 반복·투명 배경이다", ({ src, frames, totalMs }) => {
    const gif = readGif(publicFile(src));
    expect([gif.width, gif.height]).toEqual([160, 160]);
    expect(gif.frames).toBe(frames);
    expect(gif.delays.reduce((a, b) => a + b, 0)).toBe(totalMs);
    expect(gif.infinite).toBe(true);
    expect(gif.transparent).toBe(true);
  });

  it.each(specs)("$name: 원본(약 2MB)보다 훨씬 작다(400KB 이하)", ({ src }) => {
    expect(statSync(publicFile(src)).size).toBeLessThan(400 * 1024);
  });

  it("정지 PNG 도 160×160 이라 두 GIF 와 같은 크기 — 로딩 → 완료 전환에서 로고가 튀지 않는다", () => {
    expect(pngSize(publicFile(SPINNER_DONE_SRC))).toEqual([160, 160]);
    expect(statSync(publicFile(SPINNER_DONE_SRC)).size).toBeLessThan(40 * 1024);
  });

  it("큰 원본(800·512px)은 저장소에 올리지 않는다", () => {
    for (const name of ["skovix-spinner-transparent.gif", "skovix-ai-loading.gif", "skovix-spinner-front.png"]) {
      expect(existsSync(resolve(root, "public", name)), name).toBe(false);
    }
  });
});

describe("로딩 스피너 교체", () => {
  /** 이 화면 전용(/search-classic) 부품 — 초기 화면 보존이라 스피너도 그대로 둔다 */
  const CLASSIC_ONLY = new Set([
    "pages/search-classic.vue",
    "components/TopResult.vue",
    "components/SearchInput.vue",
    "components/BookCard.vue",
    "components/ChatHistory.vue",
    "components/CategoryAccordion.vue",
    "components/BookChat.legacy.vue",
  ]);

  function vueFiles(dir: string): string[] {
    return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
      e.isDirectory() ? vueFiles(join(dir, e.name)) : e.name.endsWith(".vue") ? [join(dir, e.name)] : [],
    );
  }
  const files = [...vueFiles(resolve(root, "pages")), ...vueFiles(resolve(root, "components"))].map((f) =>
    relative(root, f).split("\\").join("/"),
  );

  it("/img/ico-spinner.svg 참조는 /search-classic 전용 부품 밖에 남아 있지 않다", () => {
    const left = files.filter((f) => !CLASSIC_ONLY.has(f) && read(f).includes("ico-spinner.svg"));
    expect(left).toEqual([]);
  });

  it('로딩 스피너는 모두 :src="SPINNER_SRC" 한 상수를 쓴다(기본 변형을 바꾸려면 상수 한 줄)', () => {
    const users = files.filter((f) => /:src="[^"]*\bSPINNER_SRC\b/.test(read(f)));
    expect(users.sort()).toEqual(
      [
        "components/AiResultPanel.vue",
        "components/work/ProposalStep.vue",
        "components/work/ReadingStep.vue",
        "components/work/TopicsStep.vue",
        "pages/books/[cnts_id].vue",
        "pages/index.vue",
        "pages/papers/[id].vue",
        "pages/papers/index.vue",
        "pages/recommend/[id].vue",
        "pages/research/[id].vue",
      ].sort(),
    );
    // 새 스피너의 경로를 화면에 직접 쓰지 않는다
    for (const f of files) expect(read(f), f).not.toMatch(/src="\/skovix-spinner-/);
  });

  it("직접 import 하는 화면은 ~/utils/brand 에서 가져온다(연구 화면·work 부품은 Nuxt 자동 가져오기에 맡겨 줄을 늘리지 않는다)", () => {
    const direct = [
      "pages/index.vue",
      "pages/papers/index.vue",
      "pages/papers/[id].vue",
      "pages/books/[cnts_id].vue",
      "pages/recommend/[id].vue",
      "components/AiResultPanel.vue",
    ];
    for (const f of direct) {
      expect(read(f), f).toMatch(/import \{[^}]*\bSPINNER_SRC\b[^}]*\} from "~\/utils\/brand"/);
    }
  });

  it("옛 아이콘 파일은 지우지 않는다(/search-classic 이 쓴다)", () => {
    expect(existsSync(resolve(root, "public/img/ico-spinner.svg"))).toBe(true);
    expect(existsSync(resolve(root, "public/ic_ing.gif"))).toBe(true);
    expect(existsSync(resolve(root, "public/ic_done.png"))).toBe(true);
  });

  it("AI 패널 로고: 받는 중은 스피너, 끝나면 정지 그림이고 TopResult 는 그대로 ic_done.png 다", () => {
    expect(read("components/AiResultPanel.vue")).toContain(':src="loading ? SPINNER_SRC : SPINNER_DONE_SRC"');
    expect(read("components/TopResult.vue")).toContain('src="/ic_done.png"');
  });
});

describe("CSS — 새 스피너는 스스로 도니 CSS 회전을 걸지 않는다", () => {
  const css = read("assets/css/style_skovix.css").replace(/\/\*[\s\S]*?\*\//g, "");

  it(".skx-book__spinner 에 회전·색 변환이 없고 skx-spin 키프레임도 걷었다", () => {
    const rule = css.match(/\n\.skx-book__spinner\s*\{[^}]*\}/)?.[0] ?? "";
    expect(rule).not.toBe("");
    expect(rule).not.toMatch(/animation|filter|rotate/);
    expect(css).not.toMatch(/skx-spin(?![\w-])/);
  });

  it("새 스피너 그림에는 테마 필터 토큰(--skx-spinner-filter)만 두르고, 연구 화면 스피너에도 회전이 없다", () => {
    expect(css).toMatch(/:where\(img\[src\*="\/skovix-spinner-"\]\)\s*\{\s*filter:\s*var\(--skx-spinner-filter\);/);
    expect(read("assets/css/research.css")).not.toMatch(/\.rs-spinner\s*\{[^}]*animation/);
  });
});
