// frontend/tests/unit/historyLegacy.test.ts
import { describe, expect, it, vi } from "vitest";
import type { HistoryImportItem, HistoryImportOut, LegacyHistoryEntry } from "~/types/history";
import {
  LEGACY_BACKUP_KEY,
  LEGACY_HISTORY_KEY,
  LEGACY_MIGRATED_KEY,
  V1_MAP_KEY,
  convertLegacy,
  findRecentDuplicate,
  migrateLegacy,
  normalizeTitle,
  readV1Map,
} from "~/utils/historyStore";
import { MemoryStorage } from "./helpers/memoryStorage";
import { ID1, ID2, bookEntry, networkError, paperEntry, researchEntry } from "./helpers/fakeHistory";

const V1_BOOK = {
  id: "1727000000000",
  type: "book",
  query: "  한국 경제 책  ",
  timestamp: "2026-09-20T01:02:03.000Z",
  result: {
    mode: "book",
    query: "한국 경제 책",
    rewritten_query: "한국 경제",
    books: [
      {
        book_id: "B1",
        best_score: 0.8,
        chunks: [{ text: "본문" }],
        book_info: { title: "경제학", summary: "긴 요약" },
      },
    ],
  },
  aiSummary: JSON.stringify({ intro: "소개", items: [{ book_id: "B1", reason: "이유" }] }),
};

const V1_PAPER = {
  id: "1727000000001",
  type: "paper",
  query: "딥러닝",
  timestamp: 1727000000001,
  aiSummary: JSON.stringify({ text: "요약", refs: [{ num: 1 }] }),
};

function v1(n: number) {
  return Array.from({ length: n }, (_, i) => ({ ...V1_BOOK, id: String(1727000000000 + i) }));
}

function importer(fail?: unknown) {
  return {
    importItems: vi.fn(async (items: HistoryImportItem[]): Promise<HistoryImportOut> => {
      if (fail) throw fail;
      return {
        imported: items.length,
        skipped: 0,
        id_map: Object.fromEntries(items.map((i) => [i.legacy_id!, `uuid-${i.legacy_id}`])),
      };
    }),
  };
}

describe("convertLegacy", () => {
  it("type·query·timestamp·aiSummary 를 v2 로 옮기고 결과는 축약한다", () => {
    const [book] = convertLegacy([V1_BOOK] as LegacyHistoryEntry[]);
    expect(book).toMatchObject({
      legacy_id: "1727000000000",
      kind: "book",
      title: "한국 경제 책",
      params: {},
      ref_id: null,
      created_at: "2026-09-20T01:02:03.000Z",
      ai: { intro: "소개", items: [{ book_id: "B1", reason: "이유" }] },
    });
    expect(book!.snapshot).toEqual({
      query: "한국 경제 책",
      rewritten_query: "한국 경제",
      books: [{ book_id: "B1", best_score: 0.8, chunks: [], book_info: { title: "경제학" } }],
    });
  });

  it("논문 요약 JSON 과 JSON 이 아닌 옛 문자열을 모두 받는다", () => {
    const [paper, plainPaper, plainBook] = convertLegacy([
      V1_PAPER,
      { ...V1_PAPER, id: "2", aiSummary: "그냥 글" },
      { ...V1_BOOK, id: "3", aiSummary: "책 소개 글" },
    ] as LegacyHistoryEntry[]);
    expect(paper!.ai).toEqual({ text: "요약", refs: [{ num: 1 }] });
    expect(plainPaper!.ai).toEqual({ text: "그냥 글", refs: [] });
    expect(plainBook!.ai).toEqual({ intro: "책 소개 글", items: [] });
  });

  it("숫자 시각은 ISO 로, 읽을 수 없는 시각은 옛 id(Date.now)로 대신한다", () => {
    const [a, b] = convertLegacy([
      V1_PAPER,
      { ...V1_PAPER, id: "1727000000999", timestamp: "어제" },
    ] as LegacyHistoryEntry[]);
    expect(a!.created_at).toBe(new Date(1727000000001).toISOString());
    expect(a!.snapshot).toBeNull();
    expect(b!.created_at).toBe(new Date(1727000000999).toISOString());
  });

  it("형식이 틀린 항목은 건너뛰고 같은 옛 id 는 한 번만 올린다", () => {
    const out = convertLegacy([
      V1_BOOK,
      V1_BOOK,
      { id: "9", type: "chat", query: "x" },
      { id: "8", type: "book", query: "   " },
      null,
      "문자열",
    ] as unknown as LegacyHistoryEntry[]);
    expect(out.map((i) => i.legacy_id)).toEqual(["1727000000000"]);
  });

  it("제목은 500자로 자른다", () => {
    const [e] = convertLegacy([{ ...V1_BOOK, query: "가".repeat(600) }] as LegacyHistoryEntry[]);
    expect(e!.title).toHaveLength(500);
  });
});

describe("readV1Map", () => {
  it("대응표를 읽고 깨졌으면 빈 표", () => {
    const s = new MemoryStorage();
    expect(readV1Map(s)).toEqual({});
    s.setItem(V1_MAP_KEY, JSON.stringify({ "1727": ID1, bad: 3 }));
    expect(readV1Map(s)).toEqual({ "1727": ID1 });
    s.setItem(V1_MAP_KEY, "깨짐");
    expect(readV1Map(s)).toEqual({});
    expect(readV1Map(null)).toEqual({});
  });
});

describe("migrateLegacy", () => {
  it("v1 이 없으면 아무것도 하지 않는다", async () => {
    const server = importer();
    expect(await migrateLegacy(new MemoryStorage(), server)).toBeNull();
    expect(server.importItems).not.toHaveBeenCalled();
  });

  it("올린 뒤 원본을 백업 키로 옮기고 대응표를 남긴다", async () => {
    const s = new MemoryStorage();
    const raw = JSON.stringify(v1(2));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    expect(await migrateLegacy(s, importer())).toEqual({ imported: 2 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBeNull();
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe(raw);
    expect(readV1Map(s)).toEqual({
      "1727000000000": "uuid-1727000000000",
      "1727000000001": "uuid-1727000000001",
    });
  });

  it("서버가 실패하면 v1 을 그대로 두고 null", async () => {
    const s = new MemoryStorage();
    const raw = JSON.stringify(v1(1));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    expect(await migrateLegacy(s, importer(networkError()))).toBeNull();
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(raw);
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBeNull();
    expect(s.getItem(V1_MAP_KEY)).toBeNull();
  });

  it("100건씩 나눠 올린다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_HISTORY_KEY, JSON.stringify(v1(101)));
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 101 });
    expect(server.importItems.mock.calls.map(([items]) => items.length)).toEqual([100, 1]);
  });

  it("이미 백업이 있으면 덮어쓰지 않고 새 키에 둔다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_BACKUP_KEY, "옛 백업");
    s.setItem(LEGACY_HISTORY_KEY, JSON.stringify(v1(1)));
    await migrateLegacy(s, importer());
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe("옛 백업");
    const extra = Array.from({ length: s.length }, (_, i) => s.key(i)).filter((k) =>
      k?.startsWith(`${LEGACY_BACKUP_KEY}_`),
    );
    expect(extra).toHaveLength(1);
  });

  it("사본 둘 자리가 없으면 원본을 남기고 다시 올리지 않게 표시한다", async () => {
    const raw = JSON.stringify(v1(5));
    const s = new MemoryStorage(Math.floor(raw.length * 1.5));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 5 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(raw);
    expect(s.getItem(LEGACY_MIGRATED_KEY)).toBe("1");
    expect(await migrateLegacy(s, server)).toBeNull();
    expect(server.importItems).toHaveBeenCalledTimes(1);
  });

  it("올리는 사이 구버전 탭이 v1 을 다시 쓰면 v1 을 남겨 다음 로드에 다시 올린다", async () => {
    const s = new MemoryStorage();
    const raw = JSON.stringify(v1(1));
    const rewritten = JSON.stringify([{ ...V1_BOOK, id: "1727000009999" }, ...v1(1)]);
    s.setItem(LEGACY_HISTORY_KEY, raw);
    const server = importer();
    const base = server.importItems.getMockImplementation()!;
    server.importItems.mockImplementationOnce(async (items) => {
      s.setItem(LEGACY_HISTORY_KEY, rewritten);
      return base(items);
    });

    expect(await migrateLegacy(s, server)).toEqual({ imported: 1 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(rewritten);
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe(raw);

    expect(await migrateLegacy(s, server)).toEqual({ imported: 2 });
    expect(server.importItems.mock.calls[1]![0].map((i) => i.legacy_id)).toEqual(["1727000009999", "1727000000000"]);
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBeNull();
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe(raw);
    const extra = Array.from({ length: s.length }, (_, i) => s.key(i)).filter((k) =>
      k?.startsWith(`${LEGACY_BACKUP_KEY}_`),
    );
    expect(extra.map((k) => s.getItem(k!))).toEqual([rewritten]);
  });

  it("사본 둘 자리가 없어도 올리는 사이 v1 이 바뀌었으면 다시 올리지 않게 표시하지 않는다", async () => {
    const raw = JSON.stringify(v1(5));
    const rewritten = JSON.stringify([{ ...V1_BOOK, id: "1727000009999" }, ...v1(5)]);
    const s = new MemoryStorage(Math.floor(raw.length * 1.5));
    s.setItem(LEGACY_HISTORY_KEY, raw);
    const server = importer();
    const base = server.importItems.getMockImplementation()!;
    server.importItems.mockImplementationOnce(async (items) => {
      s.setItem(LEGACY_HISTORY_KEY, rewritten);
      return base(items);
    });

    expect(await migrateLegacy(s, server)).toEqual({ imported: 5 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(rewritten);
    expect(s.getItem(LEGACY_MIGRATED_KEY)).toBeNull();

    expect(await migrateLegacy(s, server)).toEqual({ imported: 6 });
    expect(s.getItem(LEGACY_HISTORY_KEY)).toBe(rewritten);
    expect(s.getItem(LEGACY_MIGRATED_KEY)).toBe("1");
  });

  it("깨진 v1 도 원문 그대로 백업으로 옮긴다", async () => {
    const s = new MemoryStorage();
    s.setItem(LEGACY_HISTORY_KEY, "[깨짐");
    const server = importer();
    expect(await migrateLegacy(s, server)).toEqual({ imported: 0 });
    expect(server.importItems).not.toHaveBeenCalled();
    expect(s.getItem(LEGACY_BACKUP_KEY)).toBe("[깨짐");
  });
});

describe("중복 판정", () => {
  const NOW = Date.parse("2026-09-26T03:00:00.000Z");
  const minutesAgo = (m: number) => new Date(NOW - m * 60_000).toISOString();

  it("normalizeTitle 은 앞뒤 공백·연속 공백·대소문자를 맞춘다", () => {
    expect(normalizeTitle("  Deep   Learning 연구 ")).toBe("deep learning 연구");
  });

  it("10분 안의 같은 종류·제목·조건이면 찾는다(조건 키 순서·빈 값 무시)", () => {
    const list = [
      paperEntry(ID1, { title: "딥러닝  연구", params: { grade: "KCI 등재", x: 1 }, createdAt: minutesAgo(5) }),
    ];
    const hit = findRecentDuplicate(
      list,
      { kind: "paper", title: "딥러닝 연구 ", params: { x: 1, grade: "KCI 등재", empty: "" } },
      NOW,
    );
    expect(hit?.id).toBe(ID1);
  });

  it("10분이 지났으면 새로 만든다 — 최근 갱신 시각 기준", () => {
    const old = [bookEntry(ID1, { createdAt: minutesAgo(30), updatedAt: minutesAgo(11) })];
    expect(findRecentDuplicate(old, { kind: "book", title: "한국 경제", params: {} }, NOW)).toBeNull();
    const touched = [bookEntry(ID1, { createdAt: minutesAgo(30), updatedAt: minutesAgo(2) })];
    expect(findRecentDuplicate(touched, { kind: "book", title: "한국 경제", params: {} }, NOW)?.id).toBe(ID1);
  });

  it("조건·종류가 다르거나 딥리서치면 찾지 않는다", () => {
    const list = [
      paperEntry(ID1, { params: { grade: "KCI 등재" }, createdAt: minutesAgo(1) }),
      researchEntry(ID2, { createdAt: minutesAgo(1) }),
    ];
    expect(findRecentDuplicate(list, { kind: "paper", title: "딥러닝 자연어 처리", params: {} }, NOW)).toBeNull();
    expect(
      findRecentDuplicate(list, { kind: "book", title: "딥러닝 자연어 처리", params: { grade: "KCI 등재" } }, NOW),
    ).toBeNull();
    expect(findRecentDuplicate(list, { kind: "research", title: "국내 AI 규제 연구 동향", params: {} }, NOW)).toBeNull();
  });
});
