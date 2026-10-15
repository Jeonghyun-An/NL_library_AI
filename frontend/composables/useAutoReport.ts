// frontend/composables/useAutoReport.ts
// 보고서 자동 산출의 절 연쇄(06e D20, spec §12-4) — [보고서 만들기]의 반영이 자동 승인한 목차에서 남은 절을 문서 순서대로
// 하나씩 넣는다. 원문 대목 고르기(리랭커·Milvus)는 FastAPI 에만 있어 워커가 목차 뒤에 절 생성을 이어 넣을 수 없다(함정 17).
// 앞 POST 의 응답(gen_id)을 받으면 다음 키를 넣고, 생성이 끝나기는 기다리지 않는다(실행 순서는 디스패처). 조건·대상은 늘
// 서버 값(목차 auto·section_gens)으로 다시 계산한다 — 탭을 닫았다 와서 보고서 화면을 열면 남은 절부터 잇는다(06e 정함 6 —
// 보고서 화면(ProposalStep)이 살아 있는 동안만 돈다). 판정은 utils/proposalView.ts 의 순수 함수다
import { getCurrentScope, onScopeDispose, ref, shallowRef, watch, type Ref } from "vue";
import type { ProposalView, WorkView } from "~/types/work";
import { autoChainOn, isNoSectionPapers, nextAutoSection } from "~/utils/proposalView";
import { workErrorMessage } from "~/utils/researchErrors";

export interface AutoReportDeps {
  proposal: Readonly<Ref<ProposalView | null>>;
  work: Readonly<Ref<WorkView | null>>;
  // 절 하나의 생성을 넣는다(POST …/sections/{key}/generate)
  generate: (key: string) => Promise<unknown>;
  // 계획서·연구를 다시 읽는다 — 조회 오류는 useResearchWork 의 errorOf 가 맡는다
  reload: () => Promise<void>;
}

export interface AutoReportHandle {
  running: Readonly<Ref<boolean>>;
  // 멈춘 까닭(workErrorMessage) — null 이면 멈추지 않았다. 화면은 [이어서 쓰기]를 보인다
  stopped: Readonly<Ref<string | null>>;
  // 409 no_section_papers 로 건너뛴 절 키(이 방문만 — 생성 기록이 남지 않아 그 방문에서는 다시 넣지 않는다)
  skipped: Readonly<Ref<ReadonlySet<string>>>;
  // [이어서 쓰기] — 멈춤을 풀고 같은 조건으로 다시 돈다
  resume: () => void;
}

const STOP_FALLBACK = "보고서를 이어 쓰지 못했습니다";

export function useAutoReport(deps: AutoReportDeps): AutoReportHandle {
  const running = ref(false);
  const stopped = ref<string | null>(null);
  const skipped = shallowRef<ReadonlySet<string>>(new Set());
  // 이 방문에서 생성을 넣은 키 — 다시 읽기 전(계획서의 section_gens 가 아직 옛 값)에도 같은 키를 또 넣지 않는다
  let requested = new Set<string>();
  let disposed = false;

  // 다음에 넣을 절. 연구의 생성 목록(이벤트로 계획서보다 먼저 바뀐다)에 절 생성이 있는 키도 뺀다 — 손으로 [이 절 쓰기]를
  // 눌렀거나 다른 탭이 넣은 절을 또 넣으면 409(이 절을 쓰는 중)로 연쇄가 멈춘다
  function next(): string | null {
    const p = deps.proposal.value;
    const w = deps.work.value;
    if (disposed || stopped.value !== null || !p || !autoChainOn(p, w)) return null;
    const skip = new Set<string>([...skipped.value, ...requested]);
    for (const g of w?.generations ?? []) if (g.kind === "section" && g.target) skip.add(g.target);
    return nextAutoSection(p, skip);
  }

  async function run(): Promise<void> {
    running.value = true;
    try {
      for (let key = next(); key !== null; key = next()) {
        try {
          await deps.generate(key);
          requested.add(key);
        } catch (e) {
          if (!isNoSectionPapers(e)) {
            // 그 밖의 4xx(쓰는 중·승인 전 등)·5xx·네트워크 — 멈추고 [이어서 쓰기]
            stopped.value = workErrorMessage(e, STOP_FALLBACK);
            break;
          }
          // 그 절에 넣을 논문이 없다 — 그 절만 '근거가 없어 쓰지 않았습니다' 를 보이고 다음 키로
          skipped.value = new Set([...skipped.value, key]);
        }
      }
      // 넣은 생성(대기 순번)과 생성 기록(section_gens)을 한 번에 맞춘다
      if (!disposed) await deps.reload().catch(() => undefined);
    } finally {
      running.value = false;
    }
    // 도는 동안의 watch 는 running 에 막혔다 — 그사이 들어온 변화로 남은 절이 생겼으면 다시 돈다
    kick();
  }

  function kick(): void {
    if (running.value || next() === null) return;
    void run();
  }

  function resume(): void {
    stopped.value = null;
    kick();
  }

  // 목차를 새로 만들면([보고서 다시 만들기] — 새 반영이라 gen_id 가 바뀐다) 이 방문의 건너뜀·멈춤·넣은 키를 비우고 새 목차로
  // 처음부터 같은 조건으로 돈다 — 묶음을 다시 나눠 근거가 생겼을 수 있다. 이미 넣은 키는 새 계획서의 생성 기록이 막는다
  watch(
    () => deps.proposal.value?.outline?.gen_id ?? null,
    (now, was) => {
      if (was === null || now === was) return;
      skipped.value = new Set();
      stopped.value = null;
      requested = new Set();
      kick();
    },
  );
  watch([() => deps.proposal.value, () => deps.work.value], () => kick(), { immediate: true });

  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true;
    });
  }

  return { running, stopped, skipped, resume };
}
