// frontend/composables/useCuration.ts
import { createCurationRequests, type CurationRequests } from "~/utils/curationRequest";
import { useApi } from "./useApi";
import { useHistory } from "./useHistory";

// 앱 전체가 한 벌을 쓴다 — 페이지가 언마운트돼도 남아야 떠나기 전에 시작한 요청을 돌아온 페이지가 이어받는다
let shared: CurationRequests | null = null;

export function useCuration(): CurationRequests {
  if (!shared) {
    const api = useApi();
    const history = useHistory();
    shared = createCurationRequests({
      request: (body) => api<unknown>("/books/curate", { method: "POST", body }),
      save: (historyId, ai) => history.patch(historyId, { ai }),
    });
  }
  return shared;
}
