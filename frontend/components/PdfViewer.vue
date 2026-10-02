<!-- frontend/components/PdfViewer.vue -->
<template>
  <Teleport to="body">
    <div class="pdf-overlay" @click.self="$emit('close')">
      <div class="pdf-modal" role="dialog" aria-modal="true" :aria-label="dialogLabel">

        <div class="pdf-header">
          <span class="pdf-title" :title="title">{{ title }}</span>
          <!-- pdf.js 를 못 읽으면(문서를 받기 전·내부 API 변경) 쪽 표시만 숨기고 뷰어는 그대로 쓴다 -->
          <template v-if="total > 0">
            <div class="pdf-pager" role="group" aria-label="쪽 이동">
              <button type="button" class="pdf-step" aria-label="이전 쪽" :aria-disabled="currentPage <= 1" @click="stepPage(-1)">‹</button>
              <span class="pdf-count">{{ currentPage }} / {{ total }}쪽</span>
              <button type="button" class="pdf-step" aria-label="다음 쪽" :aria-disabled="currentPage >= total" @click="stepPage(1)">›</button>
            </div>
            <div v-if="cited.length" class="pdf-pager pdf-pager--cite" role="group" aria-label="인용 대목 이동">
              <span class="pdf-count" aria-live="polite">인용 대목 {{ passageIdx + 1 }}/{{ cited.length }} · {{ cited[passageIdx]?.label }}</span>
              <button type="button" class="pdf-step" aria-label="이전 인용 대목" :aria-disabled="passageIdx <= 0" @click="stepPassage(-1)">‹</button>
              <button
                type="button"
                class="pdf-step"
                aria-label="다음 인용 대목"
                :aria-disabled="passageIdx >= cited.length - 1"
                @click="stepPassage(1)"
              >
                ›
              </button>
            </div>
          </template>
          <button ref="closeBtn" type="button" class="close-btn" aria-label="원문 닫기" title="닫기 (Esc)" @click="$emit('close')">✕</button>
        </div>

        <iframe
          ref="frame"
          class="pdf-frame"
          :src="viewerUrl"
          :title="`${title || '논문'} 원문`"
          allowfullscreen
          @load="onFrameLoad"
        />

      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, onBeforeUnmount, onMounted, ref } from "vue";
import type { PdfPassage } from "~/types/research";
import {
  focusReturnTarget,
  hardenPdfViewerOptions,
  pdfJsApp,
  pdfJsOptions,
  viewerOwnsEscape,
  type PdfJsApp,
} from "~/utils/pdfViewer";
import { stepChunk } from "~/utils/researchReport";

const props = defineProps<{
  cntsId: string;
  title?: string;
  page?: number;
  passages?: PdfPassage[];
}>();

const emit = defineEmits<{ close: [] }>();

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  // pdf.js 뷰어는 해시의 page 로 첫 화면 쪽을 정한다(1부터 센다)
  const hash = props.page && props.page > 0 ? `#page=${props.page}` : "";
  return `/pdfjs/web/viewer.html?file=${file}${hash}`;
});

const dialogLabel = computed(() => (props.title ? `원문 보기: ${props.title}` : "원문 보기"));
const frame = ref<HTMLIFrameElement | null>(null);
const closeBtn = ref<HTMLButtonElement | null>(null);
// pdf.js 가 알려 주는 지금 쪽·전체 쪽. 전체가 0 이면 아직 문서를 못 읽은 것이라 머리의 쪽 표시를 숨긴다
const currentPage = ref(props.page ?? 1);
const total = ref(0);
const cited = computed(() => props.passages ?? []);
const passageIdx = ref(0);
let app: PdfJsApp | null = null;

function goPage(n: number): void {
  if (!app || n === currentPage.value) return;
  app.page = n;
}

// stepChunk 는 0부터 세는 칸을 넘긴다 — 쪽은 1부터 세므로 하나 빼서 넘기고 되돌린다
function stepPage(delta: number): void {
  goPage(stepChunk(currentPage.value - 1, delta, total.value) + 1);
}

function stepPassage(delta: number): void {
  const next = stepChunk(passageIdx.value, delta, cited.value.length);
  // 끝에서 흐려진 버튼은 아무것도 하지 않는다 — 다른 쪽을 보던 뷰어가 지금 대목의 쪽으로 되돌아가지 않게
  if (next === passageIdx.value) return;
  passageIdx.value = next;
  const target = cited.value[next]?.page;
  if (target) goPage(target);
}

// pdf.js 는 run() 바로 앞에서 부모 문서에 webviewerloaded 를 보낸다(detail.source = 뷰어 창). 이 듣기에서 바꾼 설정이
// 그 실행에 쓰인다 — 글꼴 eval 을 끄고 외부 링크를 새 탭으로 연다(hardenPdfViewerOptions). 이벤트는 뷰어 창에서 만든 것이라
// instanceof CustomEvent 로 가리지 않고 detail 만 읽는다. 이 뷰어의 iframe 이 보낸 것만 받는다
function onViewerLoaded(e: Event): void {
  const win = frame.value?.contentWindow ?? null;
  if (!win || (e as CustomEvent<{ source?: unknown } | null>).detail?.source !== win) return;
  const options = pdfJsOptions(win);
  if (options) hardenPdfViewerOptions(options);
}

// iframe 이 뷰어를 읽기 시작하기 전에 듣는다 — iframe 은 마운트에서 문서에 붙으며 로드를 시작한다
onBeforeMount(() => {
  document.addEventListener("webviewerloaded", onViewerLoaded);
});

// iframe 은 로드마다 새 창이라 듣기도 매번 붙인다
async function onFrameLoad(): Promise<void> {
  const win = frame.value?.contentWindow ?? null;
  // 초점이 뷰어 안에 있으면 키 입력이 이 문서까지 오지 않는다 — Esc 는 뷰어 창에서도 듣는다.
  // 캡처로 들어야 찾기 막대가 Esc 로 먼저 닫히기 전에 열려 있었는지 볼 수 있다
  win?.addEventListener("keydown", onFrameKeydown, true);
  const found = pdfJsApp(win);
  if (!found) return;
  await found.initializedPromise;
  app = found;
  const sync = () => {
    total.value = found.pagesCount;
    currentPage.value = found.page;
  };
  found.eventBus.on("pagesinit", sync);
  found.eventBus.on("pagechanging", (evt) => {
    currentPage.value = evt.pageNumber;
  });
  // 듣기를 붙이기 전에 문서가 이미 열렸을 수 있다
  if (found.pagesCount > 0) sync();
}

function onFrameKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape" && !viewerOwnsEscape(app)) emit("close");
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") emit("close");
}

// 열려 있는 동안 배경(#__nuxt — 뷰어는 body 로 옮겨 그려진다)은 초점·클릭을 받지 않게 하고 스크롤도 묶는다.
// Tab 이 뷰어 밖으로 새지 않고, 겹친 화면을 굴려도 읽던 자리가 그대로 남는다. 스크롤바가 있던 화면은
// 그 자리를 남겨 배경이 옆으로 밀리지 않게 한다
function lockPage(on: boolean): void {
  const root = document.documentElement;
  const hasBar = window.innerWidth > root.clientWidth;
  document.getElementById("__nuxt")?.toggleAttribute("inert", on);
  root.style.overflow = on ? "hidden" : "";
  root.style.scrollbarGutter = on && hasBar ? "stable" : "";
}

// 연 순간의 초점 요소부터 위로 올라간 조상들 — 닫을 때 초점을 돌려줄 곳을 찾는다(focusReturnTarget)
const returnPath: HTMLElement[] = [];

onMounted(() => {
  for (let el = document.activeElement; el instanceof HTMLElement && el !== document.body; el = el.parentElement) {
    returnPath.push(el);
  }
  lockPage(true);
  document.addEventListener("keydown", onKeydown);
  closeBtn.value?.focus();
});

onBeforeUnmount(() => {
  document.removeEventListener("webviewerloaded", onViewerLoaded);
  document.removeEventListener("keydown", onKeydown);
  lockPage(false);
  // 배경은 그대로 있으니 돌려준 초점 때문에 화면이 움직이지 않게 한다
  focusReturnTarget(returnPath)?.focus({ preventScroll: true });
});
</script>

<style scoped>
.pdf-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.72);
  display: flex;
  align-items: center;
  justify-content: center;
}

.pdf-modal {
  display: flex;
  flex-direction: column;
  width: min(92vw, 1100px);
  height: 92vh;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
}

.pdf-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  height: 48px;
  background: #16162a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
}

.pdf-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: #e0e0f0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  border: none;
  background: rgba(255, 80, 80, 0.15);
  color: #ff8080;
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  flex-shrink: 0;
}
.close-btn:hover { background: rgba(255, 80, 80, 0.3); }

.pdf-pager {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.pdf-pager--cite {
  padding-left: 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.12);
}
.pdf-count {
  font-size: 12px;
  color: #c8c8e0;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.pdf-step {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: none;
  background: rgba(255, 255, 255, 0.08);
  color: #e0e0f0;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s;
}
.pdf-step:hover { background: rgba(255, 255, 255, 0.16); }
.pdf-step[aria-disabled="true"] {
  opacity: 0.35;
  cursor: default;
  background: rgba(255, 255, 255, 0.08);
}
.pdf-step:focus-visible,
.close-btn:focus-visible {
  outline: 2px solid #a5b4fc;
  outline-offset: 2px;
}

@media (max-width: 640px) {
  /* 좁은 화면은 제목을 한 줄 차지하게 두고 쪽·인용 대목 넘기기와 닫기를 다음 줄로 내린다 */
  .pdf-header { flex-wrap: wrap; height: auto; padding: 8px 12px; row-gap: 6px; }
  .pdf-title { flex-basis: 100%; }
  .close-btn { margin-left: auto; }
}

@media (prefers-reduced-motion: reduce) {
  .pdf-step,
  .close-btn { transition: none; }
}

.pdf-frame {
  flex: 1;
  width: 100%;
  border: none;
}
</style>
