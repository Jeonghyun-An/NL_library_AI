// frontend/utils/aiStream.ts
// AI 글 스트림(SSE) 읽기 — 논문 검색 AI 요약(/papers/summary/stream)·논문 상세 AI 요약(/papers/reason/stream)·관련 논문
// 추천 사유(/papers/related-reason/stream)·소장자료 상세 추천 이유(/books/reason/stream)가 함께 쓴다.
// 서버는 `data: {…}` 이벤트를 흘리고 끝에 `data: [DONE]` 을 보낸다. LLM 호출이 실패하면 [DONE] 바로 앞에
// `data: {"error": 문구}` 를 보낸다(app/services/search/paper_summary.py·pipeline.py) — 받은 글이 있어도 실패다.
// 부르는 쪽은 끝까지 받았을 때({ok: true})만 캐시·검색 기록에 저장하고, 실패면 받은 글에 오류 문구를 잇지 않고
// 오류로 보인다(failureText). 저장하지 않으므로 다시 열면 다시 만든다.
// DeepRead 대화는 조각 단위로 읽는 utils/deepReadSse.ts, 소장자료 추천 1권은 효과(effect)에서 끊는 utils/bookAiPick.ts 가 읽는다

// 끝까지 받았는지 — 실패의 error 는 서버가 보낸 문구, [DONE] 없이 끊겼거나 응답이 4xx·5xx 면 null
export type AiStreamEnd = { ok: true } | { ok: false; error: string | null };

const DATA = "data: ";

// 받은 이벤트(JSON 객체)를 차례로 onEvent 에 넘긴다. {error} 를 만나면 거기서 읽기를 그만둔다(그 뒤 글은 넘기지 않는다).
// 읽는 중 끊김(abort 등)은 그대로 던진다 — 부르는 쪽이 자기 signal 로 가린다
export async function readAiStream(
  resp: Response,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<AiStreamEnd> {
  if (!resp.ok || !resp.body) {
    void resp.body?.cancel().catch(() => undefined);
    return { ok: false, error: null };
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return { ok: false, error: null };
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith(DATA)) continue;
        const raw = line.slice(DATA.length).trim();
        if (raw === "[DONE]") return { ok: true };
        let event: unknown;
        try {
          event = JSON.parse(raw);
        } catch {
          continue;
        }
        if (!event || typeof event !== "object" || Array.isArray(event)) continue;
        if ("error" in event) {
          const { error } = event as { error: unknown };
          return { ok: false, error: typeof error === "string" && error.trim() ? error.trim() : null };
        }
        onEvent(event as Record<string, unknown>);
      }
    }
  } finally {
    // 일찍 끝낼 때({error}) 연결을 끊는다 — 끝까지 읽었거나 이미 끊긴 스트림의 취소 실패는 무시한다
    void reader.cancel().catch(() => undefined);
  }
}

// 화면에 보일 실패 문구 — 끝까지 받았으면 빈 글, 서버 문구가 있으면 그것, 없으면(끊김·4xx·5xx·네트워크) fallback
export function failureText(end: AiStreamEnd, fallback: string): string {
  if (end.ok) return "";
  return end.error ?? fallback;
}

// 서버 문구가 없을 때 화면이 보이는 실패 문구 — 서버 문구(paper_summary.py·pipeline.py)와 같은 말
export const AI_SUMMARY_FAILED = "AI 요약을 만들지 못했어요";
export const RELATED_REASON_FAILED = "추천 사유를 만들지 못했습니다";
export const BOOK_REASON_FAILED = "추천 이유를 만들지 못했습니다";
