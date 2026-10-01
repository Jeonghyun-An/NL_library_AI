// frontend/utils/curationRequest.ts
import type { BookAi } from "~/types/history";

export interface CurationBody {
  query: string;
  book_ids: string[];
  scores: number[];
  rewritten_query: string;
}

export interface CurationItem {
  book_id: string;
  reason: string;
}

export interface CurationResult {
  /** 서버 응답 원본 — 화면이 그대로 들고 있는다 */
  data: unknown;
  intro: string;
  items: CurationItem[];
}

export interface CurationDeps {
  request(body: CurationBody): Promise<unknown>;
  save(historyId: string, ai: BookAi): Promise<unknown>;
}

export interface CurationRequests {
  /** 끝나면 결과를, 실패하면 null 을 준다. 결과는 부른 화면이 떠났어도 historyId 기록에 저장된다 */
  run(historyId: string, body: CurationBody): Promise<CurationResult | null>;
}

type Loose = Record<string, unknown>;

function isObject(v: unknown): v is Loose {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function toResult(data: unknown): CurationResult {
  const intro = isObject(data) && typeof data.intro === "string" ? data.intro : "";
  const rawItems = isObject(data) && Array.isArray(data.items) ? data.items : [];
  const items = rawItems.filter(isObject).map((ci) => ({
    book_id: String(ci.book_id ?? ""),
    reason: String(ci.reason ?? ""),
  }));
  return { data, intro, items };
}

/**
 * 도서 큐레이션 요청을 화면 수명과 떼어 돌린다.
 * /books/curate 는 스트리밍이 아닌 단발 POST 라 연결을 끊어도 서버의 LLM 생성은 끝까지 돈다 — 끊으면 결과만 버리고,
 * 돌아온 화면이 같은 요약을 처음부터 다시 만든다. 그래서 요청은 끊지 않고 끝까지 받아 시작 때의 기록 id 로 저장하며,
 * 같은 기록의 요청이 도는 동안에는 새로 부르지 않고 그 요청을 이어받는다
 */
export function createCurationRequests(deps: CurationDeps): CurationRequests {
  const inflight = new Map<string, Promise<CurationResult | null>>();

  return {
    run(historyId, body) {
      const running = inflight.get(historyId);
      if (running) return running;
      const result = deps.request(body).then(toResult, () => null);
      inflight.set(historyId, result);
      // 저장이 끝날 때까지 붙잡아 둔다 — 그 사이 복원이 기록을 읽으면 요약이 아직 비어 있어 다시 만들려 한다
      void result
        .then((r) => (r ? deps.save(historyId, { intro: r.intro, items: r.items }) : undefined))
        .catch(() => undefined)
        .finally(() => {
          if (inflight.get(historyId) === result) inflight.delete(historyId);
        });
      return result;
    },
  };
}
