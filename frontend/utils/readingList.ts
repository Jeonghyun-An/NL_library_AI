// frontend/utils/readingList.ts
// 읽기 목록 단계(spec §4 S4·§5-4) 화면의 문구·정렬·들어온 경로. ReadingTable·PathPopover·CandidateDrawer·FunnelCounter 는
// 이 결과만 그린다. 들어온 경로는 서버에 저장된 값만 쓴다(하위질문·순위·판정·처음 채택 회차·매칭 대목과 점수·되살림)
import type { OpenPdfPayload, Verdict } from "~/types/research";
import type { ExcludedCandidate, PathChunk, ReadingFunnel, ReadingItem, ReadingView } from "~/types/work";
import { pageLabel } from "~/utils/citations";
import { citedPdfTarget } from "~/utils/pdfViewer";
import { verdictLabel } from "~/utils/researchEvents";
import { excludedPaperLine } from "~/utils/researchReport";

// 서버 경계와 같은 값(app/services/research_work/shapes.py)
export const MIN_READING_FOR_OUTLINE = 5;
export const READING_NOTE_MAX = 1000;
export const GROUP_LABEL_MAX = 60;

export interface PathLine {
  label: string;
  detail: string;
  chunk?: PathChunk;
}

export interface CandidateGroup {
  subqIdx: number;
  subquestion: string;
  items: ExcludedCandidate[];
}

const ORIGIN_LABEL: Record<ReadingItem["origin"], string> = {
  evidence: "채택 근거",
  revived: "되살림",
  broaden: "주제로 넓히기",
  related: "연관 논문",
  user: "직접 담음",
};
const VERDICTS: readonly string[] = ["pending", "sufficient", "insufficient"];
const LAST = Number.MAX_SAFE_INTEGER;
// [위로]·[아래로] 로 다시 매기는 순서 간격 — 서버 MAX_POSITION(1,000,000) 안에 넉넉하다
const POSITION_STEP = 10;

// "검토 121 → 채택 48 → 후보 31 → 담음 12" — 보고서 통계를 모르는 옛 잡은 그 칸을 뺀다
export function funnelLine(f: ReadingFunnel): string {
  const parts: string[] = [];
  if (f.reviewed != null) parts.push(`검토 ${f.reviewed}`);
  if (f.adopted != null) parts.push(`채택 ${f.adopted}`);
  parts.push(`후보 ${f.candidates}`, `담음 ${f.picked}`);
  return parts.join(" → ");
}

function minRank(item: ReadingItem): number {
  const ranks = item.path.subqs.map((s) => s.rank).filter((r): r is number => r != null);
  return ranks.length ? Math.min(...ranks) : LAST;
}

// 서버 reading_views.reading_order 와 같은 순서 — 사용자 순서(position, 없으면 뒤) → 하위질문 안 최소 순위 → cnts_id.
// 담음·뺌으로 줄을 옮기지 않는다 — 체크하는 순간 행이 손 밑에서 움직이지 않게
export function sortedItems(items: ReadingItem[]): ReadingItem[] {
  return [...items].sort(
    (a, b) =>
      (a.position ?? LAST) - (b.position ?? LAST) ||
      minRank(a) - minRank(b) ||
      (a.cnts_id < b.cnts_id ? -1 : a.cnts_id > b.cnts_id ? 1 : 0),
  );
}

// [위로]·[아래로](spec §5-4 '순서') — 표 순서(sortedItems)에서 그 행과 이웃(dir)을 맞바꾼 뒤 모든 행을 index * 10 으로
// 다시 매기고, 저장된 position 과 다른 행만 새 순서대로 돌려준다(서버 PUT 은 한 행씩 — 값마다 PUT 하나). position 이 null 인
// 행도 번호를 받는다 — 일부만 매기면 null(맨 뒤)·옛 번호와 섞여 순서가 어긋난다. 끝 행에서 바깥으로 옮기면 빈 목록
export function reorderPuts(items: ReadingItem[], cnts: string, dir: -1 | 1): { cnts: string; position: number }[] {
  const order = sortedItems(items);
  const i = order.findIndex((item) => item.cnts_id === cnts);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= order.length) return [];
  const moved = order[i]!;
  order[i] = order[j]!;
  order[j] = moved;
  return order.flatMap((item, index) => {
    const position = index * POSITION_STEP;
    return item.position === position ? [] : [{ cnts: item.cnts_id, position }];
  });
}

// [위로]·[아래로] 로 보낸 새 번호(reorderPuts 결과)를 덮은 목록 — 저장 묶음이 끝나 다시 읽기 전까지 표가 옮긴 순서를 바로
// 그린다(처음 옮기면 PUT 이 행 수만큼 나가 그것을 다 기다리면 옮긴 행이 한참 뒤에야 움직인다). 덮을 번호가 없으면 그대로
export function withPositions(items: ReadingItem[], puts: readonly { cnts: string; position: number }[]): ReadingItem[] {
  if (!puts.length) return items;
  const next = new Map(puts.map((p) => [p.cnts, p.position]));
  return items.map((item) => {
    const position = next.get(item.cnts_id);
    return position === undefined ? item : { ...item, position };
  });
}

export function originLabel(origin: ReadingItem["origin"]): string {
  return ORIGIN_LABEL[origin];
}

// 저장된 쪽수는 0부터 센다(0 은 쪽 정보 없음 — citations.pageLabel). 끝 쪽이 없으면 시작 쪽 하나로 본다
function chunkPages(chunk: PathChunk): { page_start: number; page_end: number } {
  const start = chunk.page_start ?? 0;
  return { page_start: start, page_end: chunk.page_end ?? start };
}

// [경로] 의 줄들 — 하위질문마다 '순위 · 판정 · 처음 채택 회차' 한 줄과 매칭 대목 줄, 되살림·직접 담음 줄
export function pathLines(item: ReadingItem): PathLine[] {
  const lines: PathLine[] = [];
  for (const sq of item.path.subqs) {
    const facts = [
      sq.subquestion.trim(),
      sq.rank != null ? `${sq.rank}위` : "",
      sq.verdict && VERDICTS.includes(sq.verdict) ? verdictLabel(sq.verdict as Verdict) : "",
      sq.first_round != null ? `${sq.first_round}회차에 처음 채택` : "",
    ].filter(Boolean);
    lines.push({ label: `하위질문 ${sq.idx + 1}`, detail: facts.join(" · ") });
    for (const chunk of sq.chunks) {
      lines.push({
        label: `대목 ${pageLabel(chunkPages(chunk))}`,
        detail: chunk.score != null ? `매칭 점수 ${chunk.score.toFixed(2)}` : "매칭 점수 없음",
        chunk,
      });
    }
  }
  const revived = item.path.revived;
  if (revived) {
    const round = revived.round != null ? ` ${revived.round}회차` : "";
    const note = revived.note.trim() ? ` — ${revived.note.trim()}` : "";
    lines.push({
      label: "되살림",
      detail: `하위질문 ${revived.subq_idx + 1} 「${revived.subquestion}」${round}에서 critic 이 뺀 논문${note}`,
    });
  }
  if (item.path.user) lines.push({ label: "직접 담음", detail: "빠른검색 결과에서 담은 논문입니다" });
  if (!lines.length) lines.push({ label: "들어온 경로", detail: "저장된 경로가 없습니다" });
  return lines;
}

// 경로의 대목 하나로 원문을 연다 — 그 대목의 쪽에서(쪽 정보가 없으면 첫 쪽)
export function pathPdfTarget(item: ReadingItem, chunk: PathChunk): OpenPdfPayload {
  return citedPdfTarget(item.cnts_id, item.meta.title.trim() || item.cnts_id, [chunkPages(chunk)]);
}

function pickedCount(view: ReadingView): number {
  return view.items.filter((i) => i.state === "in").length;
}

// [목차 만들기] 를 못 누르는 까닭 — 서버 POST .../outline 의 409 두 가지(주제 없음·담음 5편 미만)를 먼저 알린다
export function outlineHint(view: ReadingView): string | null {
  if (view.topic_id === null) return "주제를 먼저 고르세요 — 고른 주제로 목차를 만듭니다";
  const n = pickedCount(view);
  if (n < MIN_READING_FOR_OUTLINE) {
    return `담은 논문이 ${n}편입니다 — ${MIN_READING_FOR_OUTLINE}편 이상 담으면 목차를 만들 수 있습니다`;
  }
  return null;
}

export function canMakeOutline(view: ReadingView): boolean {
  return outlineHint(view) === null;
}

// 'critic 이 뺀 논문' 서랍 — 하위질문 순으로 묶고 묶음 안은 뺀 회차 순(회차를 모르면 뒤)
export function candidateGroups(excluded: ExcludedCandidate[]): CandidateGroup[] {
  const groups = new Map<number, CandidateGroup>();
  for (const c of excluded) {
    let group = groups.get(c.subq_idx);
    if (!group) {
      group = { subqIdx: c.subq_idx, subquestion: c.subquestion, items: [] };
      groups.set(c.subq_idx, group);
    }
    group.items.push(c);
  }
  return [...groups.values()]
    .sort((a, b) => a.subqIdx - b.subqIdx)
    .map((g) => ({ ...g, items: [...g.items].sort((a, b) => (a.round ?? LAST) - (b.round ?? LAST)) }));
}

// 뺀 논문 한 줄 — 보고서·탐색 타임라인의 제외 목록과 같은 "저자 외 (연도) 「제목」"
export function candidateLine(c: ExcludedCandidate): string {
  return excludedPaperLine({ cntsId: c.cnts_id, title: c.title, personalAuthor: c.personal_author, pubDate: c.pub_date });
}

// 논문별 제외 사유는 저장되지 않는다(spec §5-4) — 뺀 회차와 그 회차의 critic 메모를 함께 보인다
export function candidateNote(c: ExcludedCandidate): string | null {
  const parts = [c.round != null ? `${c.round}회차에 뺌` : "", c.note.trim() ? `critic 메모: ${c.note.trim()}` : ""];
  const line = parts.filter(Boolean).join(" · ");
  return line || null;
}

// 메모·묶음 칸의 저장 값 — 앞뒤 공백을 지우고 비면 null(서버가 칸을 비운다)
export function fieldValue(raw: string): string | null {
  const text = raw.trim();
  return text ? text : null;
}

// 다시 읽은 목록에서 처음 보는 행(되살리기·담기로 들어온 행) — 첫 그림(prev 없음)은 강조하지 않는다
export function freshIds(prev: ReadonlySet<string> | null, next: readonly string[]): string[] {
  if (!prev) return [];
  return next.filter((id) => !prev.has(id));
}
