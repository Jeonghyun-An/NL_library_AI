// frontend/composables/useResearchWorks.ts
// 이어간 연구 목록(GET /api/research-works — ?example=1 이면 예시 연구)을 읽는다. 예시 연구 카드(메인 입력창 아래)가 쓴다
import type { WorkListItem, WorkListOut } from "~/utils/researchExamples";
import { gatherExamples, type ExampleMeta } from "~/utils/researchExamples";
import { useApi } from "./useApi";
import { useWorkApi } from "./useResearchWork";

export function useResearchWorksApi() {
  const api = useApi();
  return {
    listWorks: (example: boolean) => api<WorkListOut>("/research-works", { query: example ? { example: 1 } : {} }),
  };
}

// 메인 입력창 아래의 예시 연구 카드 — 목록과 예시마다의 실행 시각·범위(GET work 의 corpus)를 앱에서 한 번만 읽는다(랜딩을 오가거나
// DeepResearch 모드를 다시 켤 때마다 다시 읽지 않는다). 목록을 못 읽으면 null 로 두어 다음에 다시 읽고, 범위를 못 읽은 카드는 그 줄만 뺀다.
// 목록과 범위를 모두 받은 뒤 두 값을 함께 채운다(gatherExamples) — 카드가 먼저 서고 메타 줄이 뒤에 붙으면 세로 가운데 정렬인 랜딩의
// 입력창이 한 번 더 밀린다. 그동안 loading 을 내리지 않아 같은 읽기가 겹치지 않는다
export function useResearchExamples() {
  const { listWorks } = useResearchWorksApi();
  const workApi = useWorkApi();
  const examples = useState<WorkListItem[] | null>("skx:research-examples", () => null);
  const metas = useState<Record<string, ExampleMeta>>("skx:research-example-metas", () => ({}));
  const loading = useState<boolean>("skx:research-examples-loading", () => false);

  async function corpusOf(id: string) {
    try {
      return (await workApi.getWork(id)).corpus;
    } catch (e) {
      console.warn("[research] 예시 연구의 범위를 읽지 못했다", e);
      throw e;
    }
  }

  async function load(): Promise<void> {
    if (examples.value !== null || loading.value) return;
    loading.value = true;
    try {
      const got = await gatherExamples(() => listWorks(true), corpusOf);
      metas.value = got.metas;
      examples.value = got.examples;
    } catch (e) {
      console.warn("[research] 예시 연구를 읽지 못했다", e);
    } finally {
      loading.value = false;
    }
  }

  return { examples, metas, load };
}
