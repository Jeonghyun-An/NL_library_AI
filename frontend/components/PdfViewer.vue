<template>
  <Teleport to="body">
    <div class="pdf-overlay" @click.self="$emit('close')">
      <div class="pdf-modal">

        <!-- 헤더 -->
        <div class="pdf-header">
          <span class="pdf-title" :title="title">{{ title }}</span>
          <div class="pdf-nav">
            <button class="nav-btn" @click="prevPage" :disabled="page <= 1">‹</button>
            <span class="page-info">
              <input
                class="page-input"
                type="number"
                :min="1"
                :max="totalPages"
                :value="page"
                @change="onPageInput"
              />
              <span>/ {{ totalPages }}</span>
            </span>
            <button class="nav-btn" @click="nextPage" :disabled="page >= totalPages">›</button>
          </div>
          <div class="pdf-zoom">
            <button class="nav-btn" @click="changeZoom(-0.25)" :disabled="scale <= 0.5">−</button>
            <span class="zoom-label">{{ Math.round(scale * 100) }}%</span>
            <button class="nav-btn" @click="changeZoom(0.25)" :disabled="scale >= 3">+</button>
          </div>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <!-- 캔버스 영역 -->
        <div class="pdf-body" ref="bodyRef">
          <div v-if="loading" class="pdf-loading">
            <img src="/ic_ing.gif" alt="" style="width:32px" />
            <span>PDF 불러오는 중…</span>
          </div>
          <div v-else-if="error" class="pdf-error">{{ error }}</div>
          <canvas v-show="!loading && !error" ref="canvasRef" class="pdf-canvas" />
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{
  cntsId: string;
  title?: string;
}>();

defineEmits<{ close: [] }>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const bodyRef   = ref<HTMLElement | null>(null);
const page       = ref(1);
const totalPages = ref(0);
const scale      = ref(1.2);
const loading    = ref(true);
const error      = ref("");

let pdfDoc: any = null;
let renderTask: any = null;

const pdfUrl = computed(() => `/api/books/${props.cntsId}/pdf`);

async function initPdfJs() {
  const lib = await import("/pdfjs/build/pdf.mjs" as any);
  lib.GlobalWorkerOptions.workerSrc = "/pdfjs/build/pdf.worker.mjs";
  return lib;
}

async function loadPdf() {
  loading.value = true;
  error.value   = "";
  try {
    const lib = await initPdfJs();
    const task = lib.getDocument({ url: pdfUrl.value, cMapUrl: "/pdfjs/web/cmaps/", cMapPacked: true });
    pdfDoc           = await task.promise;
    totalPages.value = pdfDoc.numPages;
    await renderPage(page.value);
  } catch (e: any) {
    error.value = `PDF를 불러올 수 없습니다: ${e?.message ?? e}`;
  } finally {
    loading.value = false;
  }
}

async function renderPage(num: number) {
  if (!pdfDoc || !canvasRef.value) return;

  if (renderTask) {
    renderTask.cancel();
    renderTask = null;
  }

  const pdfPage  = await pdfDoc.getPage(num);
  const viewport = pdfPage.getViewport({ scale: scale.value });
  const canvas   = canvasRef.value;
  canvas.width   = viewport.width;
  canvas.height  = viewport.height;

  const ctx = canvas.getContext("2d")!;
  renderTask = pdfPage.render({ canvasContext: ctx, viewport });
  await renderTask.promise;
  renderTask = null;
}

async function prevPage() {
  if (page.value <= 1) return;
  page.value--;
  await renderPage(page.value);
}

async function nextPage() {
  if (page.value >= totalPages.value) return;
  page.value++;
  await renderPage(page.value);
}

async function onPageInput(e: Event) {
  const v = parseInt((e.target as HTMLInputElement).value);
  if (isNaN(v) || v < 1 || v > totalPages.value) return;
  page.value = v;
  await renderPage(page.value);
}

async function changeZoom(delta: number) {
  scale.value = Math.min(3, Math.max(0.5, Math.round((scale.value + delta) * 100) / 100));
  await renderPage(page.value);
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === "ArrowRight" || e.key === "ArrowDown") nextPage();
  if (e.key === "ArrowLeft"  || e.key === "ArrowUp")   prevPage();
}

onMounted(() => {
  loadPdf();
  window.addEventListener("keydown", onKeyDown);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeyDown);
  if (pdfDoc) { pdfDoc.destroy(); pdfDoc = null; }
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
  width: min(92vw, 960px);
  height: 92vh;
  background: #1e1e2e;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
}

/* 헤더 */
.pdf-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  height: 52px;
  background: #16162a;
  border-bottom: 1px solid rgba(255,255,255,0.08);
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

.pdf-nav,
.pdf-zoom {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.06);
  color: #c0c0d8;
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.nav-btn:hover:not(:disabled) { background: rgba(255,255,255,0.14); }
.nav-btn:disabled { opacity: 0.35; cursor: default; }

.page-info {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #a0a0c0;
  font-size: 13px;
}

.page-input {
  width: 44px;
  text-align: center;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 4px;
  color: #e0e0f0;
  font-size: 13px;
  padding: 2px 4px;
  appearance: textfield;
}
.page-input::-webkit-inner-spin-button { display: none; }

.zoom-label {
  color: #a0a0c0;
  font-size: 13px;
  min-width: 44px;
  text-align: center;
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
  margin-left: 4px;
}
.close-btn:hover { background: rgba(255, 80, 80, 0.3); }

/* 본문 */
.pdf-body {
  flex: 1;
  overflow: auto;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 20px;
  background: #28283e;
}

.pdf-canvas {
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5);
  border-radius: 2px;
  display: block;
}

.pdf-loading,
.pdf-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #a0a0c0;
  font-size: 14px;
  margin: auto;
}

.pdf-error { color: #ff8080; }
</style>
