<script setup lang="ts">
// 대량 인덱싱 잡 대시보드 — 잡 목록/생성/제어 + 단계별 진행률 + 실패 그룹 재시도
// 오류: 읽기(목록·상세·실패 그룹)는 각 함수가 잡아 그 칸에 한 줄로 알리고 마지막으로 읽은 값은 남긴다(서버 장애와 '잡 없음'을 가른다).
// 제어·재시도·생성 실패도 그 자리에 한 줄. 문구는 utils/apiErrors 의 apiErrorMessage(ofetch 의 영문 e.message 는 보이지 않는다).
// 운영자용 밝은 화면(Tailwind)이라 다크 테마 토큰을 쓰는 공통 오류 컴포넌트 대신 회색 글 한 줄로 둔다 — 빨간 글은 쓰지 않는다
import { API_READ_TIMEOUT_MS } from "~/composables/useApi";
import { apiErrorMessage } from "~/utils/apiErrors";

const config = useRuntimeConfig();
const api = (config.public.apiBase as string) + "/admin/ingest-jobs";
// 읽기는 시간 제한을 둔다 — 응답 없이 붙들린 요청이 폴링을 멈춰 세우지 않게(폴링은 앞 요청이 끝나야 다음을 보낸다)
const READ = { timeout: API_READ_TIMEOUT_MS } as const;

interface Job {
  id: string;
  name: string;
  status: string;
  total_items: number;
  validation_report?: Record<string, unknown> | null;
  created_at?: string | null;
}
interface JobDetail extends Job {
  status_counts: Record<string, number>;
  stage_counts: Record<string, number>;
  done_total: number;
  remaining: number;
  rate_per_hour: number;
  eta_hours: number | null;
  extract_methods: Record<string, number>;
}
interface FailureGroup {
  error_group: string;
  count: number;
  sample_error: string;
}

const jobs = ref<Job[]>([]);
const selectedId = ref<string | null>(null);
const detail = ref<JobDetail | null>(null);
const failures = ref<FailureGroup[]>([]);
const loading = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// 칸별 오류 한 줄 — 빈 문자열이면 없다
const jobsError = ref("");
const detailError = ref("");
const controlError = ref("");
const retryError = ref("");
// 처음 목록을 받기 전에는 '잡이 없어요'를 띄우지 않는다
const jobsLoaded = ref(false);
// 재시도 중인 그룹(전체 재시도는 ALL) — 그동안 재시도 버튼을 모두 막아 같은 요청이 여러 번 가지 않게
const ALL_FAILED = "__all__";
const retrying = ref<string | null>(null);
// 늦게 온 응답이 새 응답을 덮지 않게 — 마지막으로 보낸 요청의 응답만 쓴다(잡을 바꾼 뒤 도착한 이전 잡의 상세 포함)
let jobsSeq = 0;
let detailSeq = 0;

// 오류 한 줄의 모양 — 회색 글 + 왼쪽 호박색 선(빨간 글은 쓰지 않는다). 문구의 '\n'(문장마다 줄바꿈)을 줄로 그린다
const ERROR_LINE = "text-xs text-gray-700 border-l-2 border-amber-400 pl-2 whitespace-pre-line";

const CONTROL_LABEL: Record<string, string> = {
  start: "시작",
  pause: "일시정지",
  resume: "재개",
  cancel: "취소",
};

// 생성 폼
const form = reactive({
  name: "",
  manifest_key: "",
  skip_cover: true,
  doc_type: "paper",
  high_water: 32,
});
const creating = ref(false);
const createMsg = ref("");
const createError = ref("");

const STAGES = ["pending", "extracted", "summarized", "indexed", "finalized"];
const STAGE_COLORS: Record<string, string> = {
  pending: "bg-gray-300",
  extracted: "bg-sky-400",
  summarized: "bg-indigo-400",
  indexed: "bg-violet-500",
  finalized: "bg-emerald-500",
};

// 목록 읽기 — 던지지 않는다(폴링·마운트가 await 없이 부른다). 실패하면 마지막 목록을 남기고 한 줄로 알린다
async function loadJobs(): Promise<void> {
  const seq = ++jobsSeq;
  try {
    const res = await $fetch<{ jobs: Job[] }>(api, READ);
    if (seq !== jobsSeq) return;
    jobs.value = res.jobs;
    jobsError.value = "";
    jobsLoaded.value = true;
    const firstJob = jobs.value[0];
    if (!selectedId.value && firstJob) selectJob(firstJob.id);
  } catch (e) {
    if (seq !== jobsSeq) return;
    jobsError.value = apiErrorMessage(e, "잡 목록을 불러오지 못했어요");
  }
}

// 상세·실패 그룹 읽기 — 던지지 않는다. 실패하면 마지막 값을 남기고(잡을 바꾼 직후면 비어 있다) 한 줄로 알린다
async function loadDetail(): Promise<void> {
  const id = selectedId.value;
  if (!id) return;
  const seq = ++detailSeq;
  try {
    const [d, f] = await Promise.all([
      $fetch<JobDetail>(`${api}/${id}`, READ),
      $fetch<{ groups: FailureGroup[] }>(`${api}/${id}/failures`, READ),
    ]);
    if (seq !== detailSeq) return;
    detail.value = d;
    failures.value = f.groups;
    detailError.value = "";
  } catch (e) {
    if (seq !== detailSeq) return;
    detailError.value = apiErrorMessage(e, "잡 상세를 불러오지 못했어요");
  }
}

function selectJob(id: string) {
  if (selectedId.value !== id) {
    // 다른 잡의 상세·오류가 새 잡 자리에 남지 않게 비우고 읽는다
    detail.value = null;
    failures.value = [];
    detailError.value = "";
    controlError.value = "";
    retryError.value = "";
  }
  selectedId.value = id;
  void loadDetail();
}

// 앞 폴링이 끝나기 전에는 다음 폴링을 보내지 않는다 — 응답이 느리면 요청이 겹쳐 쌓였다
let polling = false;
async function poll(): Promise<void> {
  if (polling) return;
  polling = true;
  try {
    await Promise.all([loadJobs(), loadDetail()]);
  } finally {
    polling = false;
  }
}

async function control(action: string) {
  const id = selectedId.value;
  if (!id || loading.value) return;
  loading.value = true;
  controlError.value = "";
  try {
    await $fetch(`${api}/${id}/${action}`, { method: "POST" });
  } catch (e) {
    controlError.value = apiErrorMessage(e, `잡을 ${CONTROL_LABEL[action] ?? action}하지 못했어요`);
    return;
  } finally {
    loading.value = false;
  }
  // 제어는 이미 됐다 — 뒤의 다시 읽기가 실패하면 그 칸이 따로 알린다
  await Promise.all([loadJobs(), loadDetail()]);
}

async function sendRetry(key: string, body: Record<string, unknown>) {
  const id = selectedId.value;
  if (!id || retrying.value) return;
  retrying.value = key;
  retryError.value = "";
  try {
    await $fetch(`${api}/${id}/retry`, { method: "POST", body });
  } catch (e) {
    retryError.value = apiErrorMessage(e, "재시도하지 못했어요");
    return;
  } finally {
    retrying.value = null;
  }
  await loadDetail();
}

function retryGroup(group: string) {
  return sendRetry(group, { error_group: group });
}

function retryAllFailed() {
  return sendRetry(ALL_FAILED, { all_failed: true });
}

// 생성 실패의 서버 사유('잡 생성 실패: …' — app/api/ingest_jobs.py 가 매니페스트 검증 오류 등을 붙여 400 으로 준다)는 운영자가 고칠 곳을
// 알아야 해 그 문구(한글이 든 문자열 detail)면 그대로 보인다. 그 밖(네트워크·시간 초과·프레임워크의 영문 'Not Found' 등)은 apiErrorMessage.
// ofetch 의 영문 e.message 는 쓰지 않는다
function createErrorMessage(e: unknown): string {
  const detail = (e as { data?: { detail?: unknown } } | null)?.data?.detail;
  return typeof detail === "string" && /[가-힣]/.test(detail) ? detail.trim() : apiErrorMessage(e, "잡을 만들지 못했어요");
}

async function createJob() {
  if (creating.value) return;
  creating.value = true;
  createMsg.value = "";
  createError.value = "";
  let res: { job_id: string; validation_report: Record<string, number> } | null = null;
  try {
    res = await $fetch<{
      job_id: string;
      validation_report: Record<string, number>;
    }>(api, {
      method: "POST",
      body: {
        name: form.name,
        manifest_key: form.manifest_key,
        params: {
          skip_cover: form.skip_cover,
          doc_type: form.doc_type,
          high_water: form.high_water,
        },
      },
    });
  } catch (e) {
    createError.value = createErrorMessage(e);
    return;
  } finally {
    creating.value = false;
  }
  if (!res) return;
  // 잡은 이미 만들어졌다 — 뒤의 목록 읽기가 실패해도 '생성됨'을 남긴다(실패로 보이면 다시 눌러 같은 잡이 또 생긴다).
  // 목록 실패는 목록 칸이 따로 알린다
  const r = res.validation_report;
  createMsg.value = `생성됨: 적재 ${r.to_ingest}건 (중복 ${r.duplicates}, 메타없음 ${r.missing_meta}, 파일없음 ${r.missing_object}, 기존완료 ${r.already_embedded})`;
  await loadJobs();
  selectJob(res.job_id);
}

function pct(n: number, total: number) {
  return total > 0 ? (n / total) * 100 : 0;
}

const statusBadge: Record<string, string> = {
  running: "bg-emerald-100 text-emerald-700",
  ready: "bg-sky-100 text-sky-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-gray-100 text-gray-600",
  completed_with_errors: "bg-orange-100 text-orange-700",
  canceled: "bg-rose-100 text-rose-700",
};

onMounted(() => {
  void loadJobs();
  pollTimer = setInterval(() => void poll(), 5000);
});
onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});
</script>

<template>
  <div class="min-h-screen bg-gray-50 p-6">
    <h1 class="text-2xl font-bold mb-6">대량 인덱싱 잡 대시보드</h1>

    <div class="grid grid-cols-12 gap-6">
      <!-- 좌: 잡 목록 + 생성 -->
      <div class="col-span-4 space-y-4">
        <div class="bg-white rounded-xl shadow-sm p-4">
          <h2 class="font-semibold mb-3">새 잡 생성</h2>
          <div class="space-y-2 text-sm">
            <input
              v-model="form.name"
              placeholder="잡 이름 (예: papers-round1)"
              class="w-full border rounded px-2 py-1.5"
            />
            <input
              v-model="form.manifest_key"
              placeholder="manifest_key (manifests/round1/manifest.jsonl)"
              class="w-full border rounded px-2 py-1.5"
            />
            <div class="flex gap-2 items-center">
              <label class="flex items-center gap-1">
                <input type="checkbox" v-model="form.skip_cover" /> 표지 생략
              </label>
              <select v-model="form.doc_type" class="border rounded px-2 py-1">
                <option value="paper">paper</option>
                <option value="book">book</option>
                <option value="literature">literature</option>
                <option value="policy">policy</option>
              </select>
              <input
                type="number"
                v-model.number="form.high_water"
                class="w-20 border rounded px-2 py-1"
              />
            </div>
            <button
              @click="createJob"
              :disabled="creating || !form.name || !form.manifest_key"
              class="w-full bg-violet-600 text-white rounded py-1.5 disabled:opacity-40"
            >
              {{ creating ? "검증 중…" : "생성 (dry-run 검증)" }}
            </button>
            <p v-if="createMsg" class="text-xs text-gray-600">
              {{ createMsg }}
            </p>
            <p v-if="createError" role="alert" :class="ERROR_LINE">{{ createError }}</p>
          </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-4">
          <h2 class="font-semibold mb-3">잡 목록</h2>
          <p v-if="jobsError" role="alert" :class="[ERROR_LINE, 'mb-2']">{{ jobsError }}</p>
          <ul class="space-y-1">
            <li
              v-for="j in jobs"
              :key="j.id"
              @click="selectJob(j.id)"
              :class="[
                'cursor-pointer rounded px-3 py-2 text-sm flex justify-between items-center',
                selectedId === j.id
                  ? 'bg-violet-50 ring-1 ring-violet-300'
                  : 'hover:bg-gray-50',
              ]"
            >
              <div>
                <div class="font-medium">{{ j.name }}</div>
                <div class="text-xs text-gray-400">{{ j.total_items }}건</div>
              </div>
              <span
                :class="[
                  'text-xs px-2 py-0.5 rounded',
                  statusBadge[j.status] || 'bg-gray-100',
                ]"
              >
                {{ j.status }}
              </span>
            </li>
            <!-- 목록을 받은 뒤에만 — 읽지 못한 때는 위 오류 줄이 말한다(서버 장애를 '잡이 없어요'로 보이지 않게) -->
            <li v-if="jobsLoaded && !jobs.length && !jobsError" class="text-sm text-gray-400 px-3 py-2">
              잡이 없어요
            </li>
          </ul>
        </div>
      </div>

      <!-- 우: 상세 -->
      <div class="col-span-8 space-y-4">
        <p v-if="detailError" role="alert" :class="ERROR_LINE">{{ detailError }}</p>
        <div v-if="detail" class="bg-white rounded-xl shadow-sm p-5">
          <div class="flex justify-between items-start mb-4">
            <div>
              <h2 class="text-lg font-semibold">{{ detail.name }}</h2>
              <span
                :class="[
                  'text-xs px-2 py-0.5 rounded',
                  statusBadge[detail.status] || 'bg-gray-100',
                ]"
              >
                {{ detail.status }}
              </span>
            </div>
            <div class="flex gap-2 text-sm">
              <button
                @click="control('start')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-emerald-500 text-white disabled:opacity-40"
              >
                시작
              </button>
              <button
                @click="control('pause')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-amber-500 text-white disabled:opacity-40"
              >
                일시정지
              </button>
              <button
                @click="control('resume')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-sky-500 text-white disabled:opacity-40"
              >
                재개
              </button>
              <button
                @click="control('cancel')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-rose-500 text-white disabled:opacity-40"
              >
                취소
              </button>
            </div>
          </div>
          <p v-if="controlError" role="alert" :class="[ERROR_LINE, 'mb-4']">{{ controlError }}</p>

          <!-- 진행 지표 -->
          <div class="grid grid-cols-4 gap-3 mb-4 text-center">
            <div class="bg-gray-50 rounded-lg p-3">
              <div class="text-2xl font-bold">{{ detail.done_total }}</div>
              <div class="text-xs text-gray-500">
                완료 / {{ detail.total_items }}
              </div>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <div class="text-2xl font-bold">{{ detail.remaining }}</div>
              <div class="text-xs text-gray-500">남음</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <div class="text-2xl font-bold">{{ detail.rate_per_hour }}</div>
              <div class="text-xs text-gray-500">건/시간 (최근 1h)</div>
            </div>
            <div class="bg-gray-50 rounded-lg p-3">
              <div class="text-2xl font-bold">
                {{ detail.eta_hours ?? "—" }}
              </div>
              <div class="text-xs text-gray-500">ETA (시간)</div>
            </div>
          </div>

          <!-- 단계별 스택드 진행 바 -->
          <div class="mb-2 text-sm font-medium text-gray-600">
            단계별 진행 (체크포인트)
          </div>
          <div class="flex w-full h-6 rounded overflow-hidden mb-1">
            <div
              v-for="s in STAGES"
              :key="s"
              :class="STAGE_COLORS[s]"
              :style="{
                width:
                  pct(detail.stage_counts[s] || 0, detail.total_items) + '%',
              }"
              :title="`${s}: ${detail.stage_counts[s] || 0}`"
            ></div>
          </div>
          <div class="flex gap-3 text-xs text-gray-500 mb-4 flex-wrap">
            <span v-for="s in STAGES" :key="s">
              <span
                :class="[
                  'inline-block w-2 h-2 rounded-full mr-1',
                  STAGE_COLORS[s],
                ]"
              ></span>
              {{ s }} {{ detail.stage_counts[s] || 0 }}
            </span>
          </div>

          <!-- status 카운트 -->
          <div class="flex gap-3 text-xs flex-wrap mb-2">
            <span
              v-for="(c, st) in detail.status_counts"
              :key="st"
              class="px-2 py-1 rounded bg-gray-100"
              >{{ st }}: {{ c }}</span
            >
          </div>
          <div
            v-if="Object.keys(detail.extract_methods).length"
            class="text-xs text-gray-400"
          >
            추출 방법:
            <span v-for="(c, m) in detail.extract_methods" :key="m"
              >{{ m }}={{ c }}
            </span>
          </div>
        </div>

        <!-- 실패 그룹 -->
        <div v-if="failures.length" class="bg-white rounded-xl shadow-sm p-5">
          <div class="flex justify-between items-center mb-3">
            <h3 class="font-semibold">실패 그룹</h3>
            <button
              @click="retryAllFailed"
              :disabled="!!retrying"
              class="text-sm px-3 py-1 rounded bg-violet-600 text-white disabled:opacity-40"
            >
              {{ retrying === ALL_FAILED ? "재시도 중…" : "전체 재시도" }}
            </button>
          </div>
          <p v-if="retryError" role="alert" :class="[ERROR_LINE, 'mb-3']">{{ retryError }}</p>
          <table class="w-full text-sm">
            <thead class="text-gray-400 text-left">
              <tr>
                <th class="py-1">그룹</th>
                <th>건수</th>
                <th>대표 오류</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="g in failures" :key="g.error_group" class="border-t">
                <td class="py-2 font-mono text-xs">{{ g.error_group }}</td>
                <td>{{ g.count }}</td>
                <td class="text-xs text-gray-500 max-w-md truncate">
                  {{ g.sample_error }}
                </td>
                <td class="text-right">
                  <button
                    @click="retryGroup(g.error_group)"
                    :disabled="!!retrying"
                    class="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 disabled:opacity-40"
                  >
                    {{ retrying === g.error_group ? "재시도 중…" : "재시도" }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 고른 잡이 없을 때만 '선택해 주세요'. 고른 잡을 읽는 중이면 '불러오는 중', 읽지 못했으면 위 오류 줄이 말한다 -->
        <div v-if="!selectedId" class="text-gray-400 text-sm p-8 text-center">
          잡을 선택해 주세요
        </div>
        <div v-else-if="!detail && !detailError" class="text-gray-400 text-sm p-8 text-center">
          불러오는 중…
        </div>
      </div>
    </div>
  </div>
</template>
