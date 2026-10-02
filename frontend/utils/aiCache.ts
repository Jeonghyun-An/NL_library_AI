// frontend/utils/aiCache.ts
// 논문 상세의 AI 요약·연관 이유를 탭 안에서 다시 쓴다 — 상세를 오갈 때마다 같은 글을 GPU 로 다시 만들지 않게.
// sessionStorage 라 탭을 닫으면 사라진다. 막힌 저장소·용량 초과는 캐시 없이 새로 만들 뿐이다
const PREFIX = "skx:ai:";
// 서버(services/search/paper_summary)는 생성 실패를 글로 보내고 스트림을 정상으로 닫는다 —
// 담아 두면 탭을 닫을 때까지 실패 문구만 다시 보인다
const FAILED_TAIL = /오류가 발생했습니다\.?\s*$/;

export function summaryCacheKey(paperId: string, question: string): string {
  return `${PREFIX}summary:${paperId}:${question}`;
}

export function relatedCacheKey(paperId: string, relatedId: string): string {
  return `${PREFIX}related:${paperId}:${relatedId}`;
}

export function readAiCache(storage: Storage | null, key: string): string | null {
  try {
    return storage?.getItem(key) || null;
  } catch {
    return null;
  }
}

export function writeAiCache(storage: Storage | null, key: string, text: string): void {
  if (!text.trim() || FAILED_TAIL.test(text)) return;
  try {
    storage?.setItem(key, text);
  } catch {
    // 용량 초과·막힌 저장소 — 다음에 다시 만든다
  }
}
