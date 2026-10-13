// frontend/tests/unit/readingList.test.ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ExcludedCandidate, PaperMeta, PathChunk, ReadingItem, ReadingSubqPath, ReadingView } from "~/types/work";
import {
  candidateGroups,
  candidateLine,
  candidateNote,
  canMakeOutline,
  fieldValue,
  firstPathChunk,
  freshIds,
  funnelLine,
  originLabel,
  outlineHint,
  pathLines,
  pathPdfTarget,
  preselectNote,
  reorderPuts,
  sortedItems,
  withPositions,
} from "~/utils/readingList";

const META: PaperMeta = {
  title: "노인의 우울과 사회적 지지",
  personal_author: "김철수",
  pub_date: "2015",
  series_title: "노인복지연구",
};

const CHUNK: PathChunk = { chunk_id: "KCI_A#3", page_start: 3, page_end: 3, score: 0.8234, text: "가족 지지가 높을수록 우울이 낮았다." };

function subq(over: Partial<ReadingSubqPath> = {}): ReadingSubqPath {
  return { idx: 0, subquestion: "노인 우울과 사회적 지지의 관계", rank: 3, verdict: "sufficient", first_round: 2, chunks: [], ...over };
}

function row(over: Partial<ReadingItem> = {}): ReadingItem {
  return {
    cnts_id: "KCI_A",
    state: "candidate",
    origin: "evidence",
    note: null,
    group_label: null,
    position: null,
    meta: META,
    path: { subqs: [], revived: null, user: false },
    ...over,
  };
}

function view(items: ReadingItem[], over: Partial<ReadingView> = {}): ReadingView {
  return {
    topic_id: 12,
    subquestions: ["노인 우울과 사회적 지지의 관계"],
    funnel: { reviewed: 121, adopted: 48, candidates: items.length, picked: 0 },
    items,
    excluded: [],
    ...over,
  };
}

function excluded(over: Partial<ExcludedCandidate> = {}): ExcludedCandidate {
  return {
    cnts_id: "KCI_X",
    title: "경력단절여성의 진로적응성",
    personal_author: "박민수; 최지은",
    pub_date: "2019-05",
    subq_idx: 1,
    subquestion: "사회적 지지 측정 도구",
    round: 2,
    note: "노인 대상이 아닌 연구가 섞였다",
    ...over,
  };
}

describe("funnelLine", () => {
  it("검토 → 채택 → 후보 → 담음을 잇고, 보고서 통계를 모르는 칸은 뺀다", () => {
    expect(funnelLine({ reviewed: 121, adopted: 48, candidates: 31, picked: 12 })).toBe("검토 121 → 채택 48 → 후보 31 → 담음 12");
    expect(funnelLine({ reviewed: null, adopted: null, candidates: 3, picked: 0 })).toBe("후보 3 → 담음 0");
  });
});

describe("sortedItems", () => {
  it("사용자 순서 → 하위질문 안 최소 순위 → cnts_id 순이고, 담음·뺌은 줄을 옮기지 않는다", () => {
    const items = [
      row({ cnts_id: "KCI_D", state: "in", path: { subqs: [subq({ rank: 5 })], revived: null, user: false } }),
      row({ cnts_id: "KCI_C", origin: "revived", path: { subqs: [], revived: null, user: false } }),
      row({ cnts_id: "KCI_B", state: "out", path: { subqs: [subq({ rank: 7 }), subq({ idx: 1, rank: 1 })], revived: null, user: false } }),
      row({ cnts_id: "KCI_A", position: 0, path: { subqs: [subq({ rank: 9 })], revived: null, user: false } }),
      row({ cnts_id: "KCI_E", path: { subqs: [subq({ rank: 5 })], revived: null, user: false } }),
    ];
    expect(sortedItems(items).map((i) => i.cnts_id)).toEqual(["KCI_A", "KCI_B", "KCI_D", "KCI_E", "KCI_C"]);
    expect(items[0]!.cnts_id).toBe("KCI_D");
  });
});

describe("reorderPuts — [위로]·[아래로]", () => {
  const ordered = [
    row({ cnts_id: "KCI_A", position: 0 }),
    row({ cnts_id: "KCI_B", position: 10 }),
    row({ cnts_id: "KCI_C", position: 20 }),
  ];

  it("위로 — 앞 행과 맞바꾸고 position 이 달라진 행만 새 순서대로 돌려준다", () => {
    expect(reorderPuts(ordered, "KCI_B", -1)).toEqual([
      { cnts: "KCI_B", position: 0 },
      { cnts: "KCI_A", position: 10 },
    ]);
  });

  it("아래로 — 뒤 행과 맞바꾼다", () => {
    expect(reorderPuts(ordered, "KCI_B", 1)).toEqual([
      { cnts: "KCI_C", position: 10 },
      { cnts: "KCI_B", position: 20 },
    ]);
  });

  it("끝 행을 바깥으로 옮기거나 없는 행이면 빈 목록이다", () => {
    expect(reorderPuts(ordered, "KCI_A", -1)).toEqual([]);
    expect(reorderPuts(ordered, "KCI_C", 1)).toEqual([]);
    expect(reorderPuts(ordered, "KCI_Z", 1)).toEqual([]);
  });

  it("position 이 null 인 행도 표 순서(sortedItems)대로 번호를 받는다", () => {
    const items = [
      row({ cnts_id: "KCI_B", path: { subqs: [subq({ rank: 2 })], revived: null, user: false } }),
      row({ cnts_id: "KCI_A", path: { subqs: [subq({ rank: 1 })], revived: null, user: false } }),
      row({ cnts_id: "KCI_C", path: { subqs: [subq({ rank: 3 })], revived: null, user: false } }),
    ];
    // 표 순서 A(1위)·B(2위)·C(3위) 에서 C 를 위로 → A·C·B
    expect(reorderPuts(items, "KCI_C", -1)).toEqual([
      { cnts: "KCI_A", position: 0 },
      { cnts: "KCI_C", position: 10 },
      { cnts: "KCI_B", position: 20 },
    ]);
  });
});

describe("withPositions — 저장이 끝나기 전 옮긴 순서", () => {
  const ids = (items: ReadingItem[]) => sortedItems(items).map((i) => i.cnts_id);
  // 아직 순서를 매기지 않은 목록 — 표 순서는 순위대로 A·B·C·D·E
  const fresh = ["KCI_A", "KCI_B", "KCI_C", "KCI_D", "KCI_E"].map((cnts_id, i) =>
    row({ cnts_id, path: { subqs: [subq({ rank: i + 1 })], revived: null, user: false } }),
  );

  it("보낸 번호를 덮으면 PUT 이 끝나기 전에도 옮긴 순서로 그린다 — 덮을 번호가 없으면 같은 목록", () => {
    const puts = reorderPuts(fresh, "KCI_E", -1);
    expect(puts).toHaveLength(5);
    expect(ids(withPositions(fresh, puts))).toEqual(["KCI_A", "KCI_B", "KCI_C", "KCI_E", "KCI_D"]);
    expect(withPositions(fresh, [])).toBe(fresh);
    expect(fresh.every((i) => i.position === null)).toBe(true);
  });

  it("앞 옮김이 다 저장된 순서로 계산한 다음 옮김은 앞 옮김을 지키고, 중간 목록으로 계산하면 앞 옮김이 사라진다", () => {
    const first = reorderPuts(fresh, "KCI_E", -1);
    const saved = withPositions(fresh, first);
    expect(ids(withPositions(saved, reorderPuts(saved, "KCI_B", -1)))).toEqual([
      "KCI_B",
      "KCI_A",
      "KCI_C",
      "KCI_E",
      "KCI_D",
    ]);
    // 첫 PUT(A=0) 하나만 반영된 중간 목록으로 B 를 올리면 E·D 의 번호를 옛 자리로 다시 보내 E 를 올린 것이 지워진다
    const partial = withPositions(fresh, first.slice(0, 1));
    const late = [...first, ...reorderPuts(partial, "KCI_B", -1)];
    expect(ids(withPositions(fresh, late))).toEqual(["KCI_B", "KCI_A", "KCI_C", "KCI_D", "KCI_E"]);
  });
});

describe("originLabel", () => {
  it("들어온 갈래마다 이름을 준다", () => {
    expect(originLabel("evidence")).toBe("채택 근거");
    expect(originLabel("revived")).toBe("되살림");
    expect(originLabel("broaden")).toBe("주제로 넓히기");
    expect(originLabel("related")).toBe("연관 논문");
    expect(originLabel("user")).toBe("직접 담음");
  });
});

describe("pathLines", () => {
  it("하위질문마다 순위·판정·처음 채택 회차 한 줄, 그 아래 매칭 대목 줄(쪽·점수)을 둔다", () => {
    const item = row({ path: { subqs: [subq({ chunks: [CHUNK] })], revived: null, user: false } });
    expect(pathLines(item)).toEqual([
      { label: "하위질문 1", detail: "노인 우울과 사회적 지지의 관계 · 3위 · 근거 충분 · 2회차에 처음 채택" },
      { label: "대목 p.4", detail: "매칭 점수 0.82", chunk: CHUNK },
    ]);
  });

  it("모르는 값(순위·판정·회차·점수·쪽)은 그 칸을 빼고 적는다", () => {
    const bare: PathChunk = { chunk_id: "KCI_A#0", page_start: null, page_end: null, score: null, text: "초록" };
    const item = row({
      path: { subqs: [subq({ idx: 1, rank: null, verdict: "unknown", first_round: null, chunks: [bare] })], revived: null, user: false },
    });
    expect(pathLines(item)).toEqual([
      { label: "하위질문 2", detail: "노인 우울과 사회적 지지의 관계" },
      { label: "대목 쪽 정보 없음", detail: "매칭 점수 없음", chunk: bare },
    ]);
  });

  it("되살린 논문은 뺀 하위질문·회차·critic 메모를, 직접 담은 논문은 그 사실을, 경로가 없으면 없다고 적는다", () => {
    const revived = row({
      origin: "revived",
      path: { subqs: [], revived: { subq_idx: 1, subquestion: "사회적 지지 측정 도구", round: 2, note: "대상이 다르다" }, user: false },
    });
    expect(pathLines(revived)).toEqual([
      { label: "되살림", detail: "하위질문 2 「사회적 지지 측정 도구」 2회차에서 critic 이 뺀 논문 — 대상이 다르다" },
    ]);
    const quiet = row({ path: { subqs: [], revived: { subq_idx: 0, subquestion: "관계", round: null, note: " " }, user: false } });
    expect(pathLines(quiet)[0]!.detail).toBe("하위질문 1 「관계」에서 critic 이 뺀 논문");
    expect(pathLines(row({ origin: "user", path: { subqs: [], revived: null, user: true } }))).toEqual([
      { label: "직접 담음", detail: "빠른검색 결과에서 담은 논문입니다" },
    ]);
    expect(pathLines(row())).toEqual([{ label: "들어온 경로", detail: "저장된 경로가 없습니다" }]);
  });
});

describe("firstPathChunk — 패널의 첫 대목", () => {
  it("[경로] 와 같은 순서의 첫 매칭 대목 — 대목이 없는 하위질문은 건너뛴다", () => {
    const second: PathChunk = { ...CHUNK, chunk_id: "KCI_A#9", page_start: 9, page_end: 10 };
    const item = row({
      path: { subqs: [subq({ chunks: [CHUNK, second] }), subq({ idx: 1, chunks: [second] })], revived: null, user: false },
    });
    expect(firstPathChunk(item)).toEqual({ label: "하위질문 1 · 대목 p.4", chunk: CHUNK });
    const later = row({ path: { subqs: [subq(), subq({ idx: 1, chunks: [second] })], revived: null, user: false } });
    expect(firstPathChunk(later)).toEqual({ label: "하위질문 2 · 대목 p.10–11", chunk: second });
  });

  it("매칭 대목이 하나도 없으면 null — 쪽을 모르는 대목은 '쪽 정보 없음'으로 적는다", () => {
    expect(firstPathChunk(row({ path: { subqs: [subq()], revived: null, user: false } }))).toBeNull();
    const bare: PathChunk = { chunk_id: "KCI_A#0", page_start: null, page_end: null, score: null, text: "초록" };
    expect(firstPathChunk(row({ path: { subqs: [subq({ chunks: [bare] })], revived: null, user: false } }))).toEqual({
      label: "하위질문 1 · 대목 쪽 정보 없음",
      chunk: bare,
    });
  });

  it("되살림·직접 담음만 있는 논문은 null", () => {
    const revived = row({
      origin: "revived",
      path: { subqs: [], revived: { subq_idx: 1, subquestion: "사회적 지지 측정 도구", round: 2, note: "" }, user: false },
    });
    expect(firstPathChunk(revived)).toBeNull();
    expect(firstPathChunk(row({ origin: "user", path: { subqs: [], revived: null, user: true } }))).toBeNull();
  });
});

describe("pathPdfTarget", () => {
  it("대목의 쪽에서 원문을 열고, 쪽을 모르면 쪽 없이 연다", () => {
    expect(pathPdfTarget(row(), CHUNK)).toEqual({
      cntsId: "KCI_A",
      title: "노인의 우울과 사회적 지지",
      page: 4,
      passages: [{ page: 4, label: "p.4" }],
    });
    const bare: PathChunk = { chunk_id: "x", page_start: null, page_end: null, score: null, text: "" };
    expect(pathPdfTarget(row({ meta: { ...META, title: " " } }), bare)).toEqual({
      cntsId: "KCI_A",
      title: "KCI_A",
      page: undefined,
      passages: [{ page: null, label: "쪽 정보 없음" }],
    });
  });
});

describe("canMakeOutline·outlineHint", () => {
  const five = ["KCI_1", "KCI_2", "KCI_3", "KCI_4", "KCI_5"].map((id) => row({ cnts_id: id, state: "in" }));

  it("주제를 고르고 담음이 5편 이상이면 만들 수 있다 — 후보·뺌은 세지 않는다", () => {
    expect(canMakeOutline(view([...five, row({ cnts_id: "KCI_6", state: "out" })]))).toBe(true);
    expect(outlineHint(view(five))).toBeNull();
  });

  it("담음이 모자라면 몇 편인지, 주제가 없으면 주제를 먼저 고르라고 알린다", () => {
    const four = [...five.slice(0, 4), row({ cnts_id: "KCI_9", state: "candidate" })];
    expect(canMakeOutline(view(four))).toBe(false);
    expect(outlineHint(view(four))).toBe("담은 논문이 4편입니다 — 5편 이상 담으면 보고서를 만들 수 있습니다");
    expect(canMakeOutline(view(five, { topic_id: null }))).toBe(false);
    expect(outlineHint(view(five, { topic_id: null }))).toBe("주제를 먼저 고르세요 — 고른 주제로 보고서를 만듭니다");
  });
});

describe("preselectNote — 이어가기가 미리 담은 채택 근거(사용자 결정 2026-10-14)", () => {
  it("미리 담은 행이 있으면 머리 안내 한 줄 — 수는 서버가 센 preselected(뺀 행도 센다)", () => {
    expect(preselectNote(view([], { preselected: 8 }))).toBe("채택 근거 상위 8편을 미리 담았습니다 — 빼거나 더할 수 있습니다");
    // 채택 근거가 여덟 편보다 적으면 모두 담는다
    expect(preselectNote(view([], { preselected: 3 }))).toBe("채택 근거 상위 3편을 미리 담았습니다 — 빼거나 더할 수 있습니다");
  });

  it("미리 담지 않았으면(이 안내 전에 이어간 연구·이 칸을 모르는 응답) 안내가 없다", () => {
    expect(preselectNote(view([], { preselected: 0 }))).toBeNull();
    expect(preselectNote(view([]))).toBeNull();
  });

  it("읽기 목록 화면 머리에 그 한 줄을 보인다", () => {
    const source = readFileSync(fileURLToPath(new URL("../../components/work/ReadingStep.vue", import.meta.url)), "utf8");
    expect(source).toMatch(/import \{[^}]*\bpreselectNote\b[^}]*\} from "~\/utils\/readingList";/);
    expect(source).toContain('<p v-if="preselectText" class="rs-muted">{{ preselectText }}</p>');
    expect(source).toContain("preselectNote(reading.value)");
  });
});

describe("critic 이 뺀 논문 서랍", () => {
  it("candidateGroups — 하위질문 순으로 묶고 묶음 안은 뺀 회차 순(모르면 뒤)", () => {
    const list = [
      excluded({ cnts_id: "KCI_X3", round: null }),
      excluded({ cnts_id: "KCI_Y", subq_idx: 0, subquestion: "노인 우울", round: 1 }),
      excluded({ cnts_id: "KCI_X2", round: 3 }),
      excluded({ cnts_id: "KCI_X1", round: 1 }),
    ];
    expect(candidateGroups(list).map((g) => [g.subqIdx, g.subquestion, g.items.map((c) => c.cnts_id)])).toEqual([
      [0, "노인 우울", ["KCI_Y"]],
      [1, "사회적 지지 측정 도구", ["KCI_X1", "KCI_X2", "KCI_X3"]],
    ]);
  });

  it("candidateLine·candidateNote — 보고서 제외 목록과 같은 한 줄, 뺀 회차와 critic 메모", () => {
    expect(candidateLine(excluded())).toBe("박민수 외 (2019) 「경력단절여성의 진로적응성」");
    expect(candidateLine(excluded({ title: "", personal_author: null, pub_date: null }))).toBe("저자 미상");
    expect(candidateNote(excluded())).toBe("2회차에 뺌 · critic 메모: 노인 대상이 아닌 연구가 섞였다");
    expect(candidateNote(excluded({ round: null }))).toBe("critic 메모: 노인 대상이 아닌 연구가 섞였다");
    expect(candidateNote(excluded({ round: null, note: "" }))).toBeNull();
  });
});

describe("fieldValue·freshIds", () => {
  it("fieldValue — 앞뒤 공백을 지우고 비면 null", () => {
    expect(fieldValue("  ")).toBeNull();
    expect(fieldValue(" 방법 비교용 ")).toBe("방법 비교용");
  });

  it("freshIds — 첫 그림은 강조하지 않고, 그 뒤 새로 들어온 행만 순서대로", () => {
    expect(freshIds(null, ["KCI_A", "KCI_B"])).toEqual([]);
    expect(freshIds(new Set(["KCI_A"]), ["KCI_A", "KCI_C", "KCI_B"])).toEqual(["KCI_C", "KCI_B"]);
    expect(freshIds(new Set(["KCI_A", "KCI_B"]), ["KCI_A"])).toEqual([]);
  });
});
