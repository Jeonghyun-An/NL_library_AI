// frontend/composables/useResearchWorks.ts
// 이어간 연구 목록(GET /api/research-works — ?example=1 이면 예시 연구)을 읽는다. 예시 연구 카드(메인 입력창 아래)가 쓴다
import type { WorkListItem, WorkListOut } from "~/utils/researchExamples";
import { exampleMeta, pickExamples, type ExampleMeta } from "~/utils/researchExamples";
import { useApi } from "./useApi";
import { useWorkApi } from "./useResearchWork";

export function useResearchWorksApi() {
  const api = useApi();
  return {
    listWorks: (example: boolean) => api<WorkListOut>("/research-works", { query: example ? { example: 1 } : {} }),
  };
}

// 메인 입력창 아래의 예시 연구 카드 — 목록과 예시마다의 실행 시각·범위(GET work 의 corpus)를 앱에서 한 번만 읽는다(랜딩을 오가거나
// DeepResearch 모드를 다시 켤 때마다 다시 읽지 않는다). 목록을 못 읽으면 null 로 두어 다음에 다시 읽고, 범위를 못 읽은 카드는 그 줄만 뺀다
export function useResearchExamples() {
  const { listWorks } = useResearchWorksApi();
  const workApi = useWorkApi();
  const examples = useState<WorkListItem[] | null>("skx:research-examples", () => null);
  const metas = useState<Record<string, ExampleMeta>>("skx:research-example-metas", () => ({}));
  const loading = useState<boolean>("skx:research-examples-loading", () => false);

  async function load(): Promise<void> {
    if (examples.value !== null || loading.value) return;
    loading.value = true;
    let list: WorkListItem[];
    try {
      list = pickExamples((await listWorks(true)).items);
    } catch (e) {
      console.warn("[research] 예시 연구를 읽지 못했다", e);
      return;
    } finally {
      loading.value = false;
    }
    examples.value = list;
    await Promise.all(
      list.map(async (ex) => {
        try {
          const work = await workApi.getWork(ex.id);
          metas.value = { ...metas.value, [ex.id]: exampleMeta(work.corpus) };
        } catch (e) {
          console.warn("[research] 예시 연구의 범위를 읽지 못했다", e);
        }
      }),
    );
  }

  return { examples, metas, load };
}
