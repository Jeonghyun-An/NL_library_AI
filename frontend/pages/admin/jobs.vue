<script setup lang="ts">
// 대량 인덱싱 잡 대시보드 — 잡 목록/생성/제어 + 단계별 진행률 + 실패 그룹 재시도
const config = useRuntimeConfig();
const api = (config.public.apiBase as string) + "/admin/ingest-jobs";

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

const STAGES = ["pending", "extracted", "summarized", "indexed", "finalized"];
const STAGE_COLORS: Record<string, string> = {
  pending: "bg-gray-300",
  extracted: "bg-sky-400",
  summarized: "bg-indigo-400",
  indexed: "bg-violet-500",
  finalized: "bg-emerald-500",
};

async function loadJobs() {
  const res = await $fetch<{ jobs: Job[] }>(api);
  jobs.value = res.jobs;
  const firstJob = jobs.value[0];
  if (!selectedId.value && firstJob) selectJob(firstJob.id);
}

async function loadDetail() {
  if (!selectedId.value) return;
  detail.value = await $fetch<JobDetail>(`${api}/${selectedId.value}`);
  const f = await $fetch<{ groups: FailureGroup[] }>(
    `${api}/${selectedId.value}/failures`,
  );
  failures.value = f.groups;
}

function selectJob(id: string) {
  selectedId.value = id;
  loadDetail();
}

async function control(action: string) {
  if (!selectedId.value) return;
  loading.value = true;
  try {
    await $fetch(`${api}/${selectedId.value}/${action}`, { method: "POST" });
    await Promise.all([loadJobs(), loadDetail()]);
  } finally {
    loading.value = false;
  }
}

async function retryGroup(group: string) {
  if (!selectedId.value) return;
  await $fetch(`${api}/${selectedId.value}/retry`, {
    method: "POST",
    body: { error_group: group },
  });
  await loadDetail();
}

async function retryAllFailed() {
  if (!selectedId.value) return;
  await $fetch(`${api}/${selectedId.value}/retry`, {
    method: "POST",
    body: { all_failed: true },
  });
  await loadDetail();
}

async function createJob() {
  creating.value = true;
  createMsg.value = "";
  try {
    const res = await $fetch<{
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
    const r = res.validation_report;
    createMsg.value = `생성됨: 적재 ${r.to_ingest}건 (중복 ${r.duplicates}, 메타없음 ${r.missing_meta}, 파일없음 ${r.missing_object}, 기존완료 ${r.already_embedded})`;
    await loadJobs();
    selectJob(res.job_id);
  } catch (e: any) {
    createMsg.value = `실패: ${e?.data?.detail || e?.message || e}`;
  } finally {
    creating.value = false;
  }
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
  loadJobs();
  pollTimer = setInterval(() => {
    loadJobs();
    if (selectedId.value) loadDetail();
  }, 5000);
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
          </div>
        </div>

        <div class="bg-white rounded-xl shadow-sm p-4">
          <h2 class="font-semibold mb-3">잡 목록</h2>
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
            <li v-if="!jobs.length" class="text-sm text-gray-400 px-3 py-2">
              잡 없음
            </li>
          </ul>
        </div>
      </div>

      <!-- 우: 상세 -->
      <div class="col-span-8 space-y-4">
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
                class="px-3 py-1 rounded bg-emerald-500 text-white"
              >
                시작
              </button>
              <button
                @click="control('pause')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-amber-500 text-white"
              >
                일시정지
              </button>
              <button
                @click="control('resume')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-sky-500 text-white"
              >
                재개
              </button>
              <button
                @click="control('cancel')"
                :disabled="loading"
                class="px-3 py-1 rounded bg-rose-500 text-white"
              >
                취소
              </button>
            </div>
          </div>

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
              class="text-sm px-3 py-1 rounded bg-violet-600 text-white"
            >
              전체 재시도
            </button>
          </div>
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
                    class="text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200"
                  >
                    재시도
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="!detail" class="text-gray-400 text-sm p-8 text-center">
          잡을 선택하세요
        </div>
      </div>
    </div>
  </div>
</template>
