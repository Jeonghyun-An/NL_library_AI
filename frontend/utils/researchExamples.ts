// frontend/utils/researchExamples.ts
// 예시 연구(06d 2부 — 사용자 결정 2026-10-13: 메인에서 DeepResearch 모드를 켰을 때 입력창 아래 카드 2~3개, 사이드바에는 두지 않는다).
// 미리 돌린 실제 연구이고 읽기 전용이다(research_works.is_example — 쓰기 API 409). 카드에 실행 시각·코퍼스 범위를 함께 보인다
// (시연 정직성 규칙 — spec §12-3). .vue 는 그리기만 한다
import type { Corpus, WorkPhase } from "~/types/work";
import { kstDateTime } from "~/utils/reportDocument";
import { scopeLine, stepForPhase } from "~/utils/workPhase";

// GET /api/research-works(?example=1) 의 items[] — app/api/research_work.py list_works(상한 50, 최근 것부터)
export interface WorkListItem {
  id: string;
  question: string;
  phase: WorkPhase;
  created_at: string | null;
}

export interface WorkListOut {
  items: WorkListItem[];
}

export interface ExampleMeta {
  ranAt: string | null;
  scope: string | null;
}

// 메인 입력창 아래 카드 수(사용자 결정 '2~3개') — 예시 질문 칸과 같은 세 칸
export const EXAMPLE_CARD_MAX = 3;

export function pickExamples(items: readonly WorkListItem[]): WorkListItem[] {
  return items.slice(0, EXAMPLE_CARD_MAX);
}

// 카드의 실행 시각·코퍼스 범위. at 은 잡이 끝난 시각(research_works.corpus_snapshot — seeds.py). 모르는 칸은 null(그 줄을 그리지 않는다)
export function exampleMeta(corpus: Corpus | null | undefined): ExampleMeta {
  const at = corpus?.at ? new Date(corpus.at) : null;
  const ranAt = at && !Number.isNaN(at.getTime()) ? `${kstDateTime(at)} 실행` : null;
  return { ranAt, scope: scopeLine(corpus) };
}

// 카드의 재료를 한 번에 모은다 — 목록(앞 EXAMPLE_CARD_MAX 개)과 예시마다의 범위(GET work 의 corpus)를 모두 받은 뒤에 함께 돌려준다.
// 랜딩은 세로 가운데 정렬이라 카드가 선 뒤 메타 줄이 따로 붙으면 입력창이 한 번 더 밀린다(P5 리뷰) — 카드는 다 갖춘 모양으로 한 번에 선다.
// 목록을 못 읽으면 거절한다(부르는 쪽이 null 로 두어 다음에 다시 읽는다). 범위를 못 읽은 예시는 metas 에서만 빠진다(카드는 질문만)
export async function gatherExamples(
  list: () => Promise<WorkListOut>,
  corpusOf: (id: string) => Promise<Corpus | null | undefined>,
): Promise<{ examples: WorkListItem[]; metas: Record<string, ExampleMeta> }> {
  const examples = pickExamples((await list()).items);
  const settled = await Promise.allSettled(examples.map((ex) => corpusOf(ex.id)));
  const metas: Record<string, ExampleMeta> = {};
  examples.forEach((ex, i) => {
    const got = settled[i];
    if (got?.status === "fulfilled") metas[ex.id] = exampleMeta(got.value);
  });
  return { examples, metas };
}

// 예시 연구는 도달한 단계 화면으로 연다 — 사이드바의 이어간 연구 줄(historyRoute.routeFor)과 같은 규칙
export function exampleRoute(item: Pick<WorkListItem, "id" | "phase">): { path: string; query: { s: string } } {
  return { path: `/research/${encodeURIComponent(item.id)}`, query: { s: stepForPhase(item.phase) } };
}
