<template>
  <Teleport to="body">
    <Transition name="cm-modal">
      <div v-if="open" class="cm-overlay" @click.self="$emit('close')">
        <div class="cm-modal">
          <div class="cm-header">
            <span>출처 인용하기</span>
            <button class="cm-close" @click="$emit('close')">×</button>
          </div>

          <div class="cm-body">
            <!-- 인용 스타일 -->
            <div class="cm-field">
              <label class="cm-field-label">인용 스타일</label>
              <select v-model="citeStyle" class="cm-select">
                <option value="APA">APA</option>
              </select>
            </div>

            <!-- 인용 언어 설정 -->
            <div class="cm-field-row">
              <label class="cm-field-label">인용 언어 설정</label>
              <div class="cm-lang-toggle">
                <button
                  :class="['cm-lang-opt', lang === 'ko' && 'active']"
                  @click="lang = 'ko'"
                >
                  국문
                </button>
                <button
                  :class="['cm-lang-opt', lang === 'en' && 'active']"
                  @click="lang = 'en'"
                >
                  영문
                </button>
              </div>
            </div>

            <!-- 참고문헌 (extra.references 목록 전체) — 부모가 넘긴 목록이라 인용문을 받는 동안에도 보인다 -->
            <div class="cm-block">
              <div class="cm-block-head">
                <span class="cm-tag">참고문헌</span>
                <button v-if="references.length" type="button" class="cm-copy" @click="copyRefs">
                  {{ copied === "refs" ? "✓ 복사됨" : "복사" }}
                </button>
              </div>
              <div v-if="references.length" ref="refsEl" class="cm-refs">
                <p
                  v-for="(ref, i) in references"
                  :key="i"
                  class="cm-ref-line"
                >
                  {{ ref }}
                </p>
              </div>
              <SkxErrorState v-else kind="empty" compact :title="PAPER_STATE_TEXT.referencesEmpty" />
              <!-- 클립보드에 쓰지 못했다(http 운영 — Clipboard API 없음) — 글을 선택해 두고 직접 복사하라고 알린다 -->
              <SkxInlineError v-if="copyFailed === 'refs'" :message="PAPER_STATE_TEXT.copyFailed" />
            </div>

            <!-- 인용 (전체 인용문 · 국문/영문 토글). 읽기 실패는 인용문 자리에 넣지 않고 따로 — 오류 문장이 인용문처럼 복사되지 않게 -->
            <div ref="citeBlockEl" class="cm-block" tabindex="-1">
              <div class="cm-block-head">
                <span class="cm-tag">인용</span>
                <button v-if="citeText && !loadError" type="button" class="cm-copy" @click="copyCite">
                  {{ copied === "cite" ? "✓ 복사됨" : "복사" }}
                </button>
              </div>
              <SkxErrorState
                v-if="loadError"
                compact
                :kind="loadError.kind"
                :title="PAPER_STATE_TEXT.citationFailed"
                :message="loadError.message"
                :busy="loading"
                :on-retry="isRetryableKind(loadError.kind) ? retryCitation : undefined"
              />
              <p v-else-if="loading" class="cm-loading">불러오는 중...</p>
              <p v-else-if="citeText" ref="citeEl" class="cm-cite">{{ citeText }}</p>
              <SkxErrorState v-else kind="empty" compact :title="PAPER_STATE_TEXT.citationEmpty" />
              <SkxInlineError v-if="copyFailed === 'cite'" :message="PAPER_STATE_TEXT.copyFailed" />
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { useApi } from "~/composables/useApi";
import { copyToClipboard } from "~/utils/clipboard";
import { isRetryableKind, PAPER_STATE_TEXT, shownError, type ShownError } from "~/utils/paperErrors";

const props = defineProps<{
  open: boolean;
  bookId: string | null;
  references: string[];
}>();
defineEmits<{ (e: "close"): void }>();

const api = useApi();

type CopyKey = "refs" | "cite";

const citeStyle = ref<"APA">("APA");
const lang = ref<"ko" | "en">("ko");
const citation = ref<{ korean: string; english: string } | null>(null);
const loading = ref(false);
// 인용문을 읽지 못했다 — 인용문 자리(korean)에 오류 문장을 넣지 않고 따로 쥔다(복사되지 않게, 영문 탭이 '없음'으로 보이지 않게)
const loadError = ref<ShownError | null>(null);
const copied = ref<"" | CopyKey>("");
// 클립보드에 쓰지 못한 칸 — 그 칸 아래에 '직접 복사해 주세요' 안내
const copyFailed = ref<"" | CopyKey>("");
const refsEl = ref<HTMLElement | null>(null);
const citeEl = ref<HTMLElement | null>(null);
const citeBlockEl = ref<HTMLElement | null>(null);
// 늦게 온 응답이 다른 논문으로 다시 연 창을 덮지 않게 — 마지막 요청만 반영한다
let loadSeq = 0;
let copiedTimer: ReturnType<typeof setTimeout> | undefined;

const citeText = computed(() =>
  !citation.value
    ? ""
    : lang.value === "ko"
      ? citation.value.korean
      : citation.value.english,
);

// 인용문을 읽는다. retry 면 실패 상태를 남긴 채(재시도 중으로) 다시 읽고, 아니면(창을 새로 엶) 이전 결과·실패를 걷고 읽는다
async function loadCitation(retry = false) {
  if (!props.bookId) return;
  const seq = ++loadSeq;
  loading.value = true;
  copied.value = "";
  copyFailed.value = "";
  if (!retry) {
    citation.value = null;
    loadError.value = null;
  }
  try {
    const data = await api<{ korean: string; english: string }>(`/papers/${props.bookId}/citation`);
    if (seq !== loadSeq) return;
    citation.value = data;
    loadError.value = null;
  } catch (e) {
    if (seq !== loadSeq) return;
    citation.value = null;
    // 이 창은 요청을 일부러 끊지 않는다 — null 이면 이유 없는 실패로 둔다
    loadError.value = shownError(e) ?? { kind: "unknown", message: "" };
  } finally {
    if (seq === loadSeq) loading.value = false;
  }
}

// [다시 시도] — 버튼이 든 상태 블록은 다 받으면 빠지므로 초점을 먼저 인용 칸으로 옮긴다
function retryCitation() {
  if (loading.value) return;
  citeBlockEl.value?.focus();
  void loadCitation(true);
}

watch(
  () => [props.open, props.bookId] as const,
  ([isOpen]) => {
    if (isOpen && props.bookId) loadCitation();
  },
  { immediate: true },
);

// 국문·영문을 바꾸면 그 칸의 복사 표시·안내를 걷는다(다른 글이다)
watch(lang, () => {
  if (copied.value === "cite") copied.value = "";
  if (copyFailed.value === "cite") copyFailed.value = "";
});

// 클립보드에 쓴다 — 못 쓰면(http 운영이라 Clipboard API 가 없음 등) 그 글을 선택해 옛 방식으로 복사하고(utils/clipboard),
// 그것도 안 되면 글을 선택해 둔 채 '직접 복사해 주세요' 안내를 그 칸 아래에 보인다
async function copyBlock(key: CopyKey, text: string, source: HTMLElement | null) {
  if (!text) return;
  copyFailed.value = "";
  const ok = await copyToClipboard(text, source);
  clearTimeout(copiedTimer);
  if (!ok) {
    copied.value = "";
    copyFailed.value = key;
    return;
  }
  copied.value = key;
  copiedTimer = setTimeout(() => (copied.value = ""), 2000);
}
function copyRefs() {
  void copyBlock("refs", props.references.join("\n"), refsEl.value);
}
function copyCite() {
  void copyBlock("cite", citeText.value, citeEl.value);
}

onBeforeUnmount(() => clearTimeout(copiedTimer));
</script>

<style scoped>
/* 검색 결과 / 상세 공용 출처 인용 모달 — 퍼블리싱 시 정밀 스타일 교체 */
.cm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.cm-modal {
  background: var(--surface);
  border-radius: var(--radius);
  width: 520px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
}
.cm-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  font-size: 15px;
  font-weight: 700;
}
.cm-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #aaa;
}
.cm-close:hover {
  color: var(--ink);
}
.cm-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}
.cm-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.cm-field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.cm-field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3, #6a6b76);
}
.cm-select {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-size: 13px;
  color: var(--ink);
  cursor: pointer;
}
.cm-lang-toggle {
  display: flex;
  gap: 4px;
  background: var(--bg);
  border-radius: 100px;
  padding: 3px;
}
.cm-lang-opt {
  border: none;
  background: none;
  padding: 5px 14px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-3, #6a6b76);
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}
.cm-lang-opt.active {
  background: var(--accent, #7c4dff);
  color: #fff;
}
.cm-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}
/* 인용 칸은 [다시 시도] 뒤 초점을 받는다(tabindex="-1") — 마우스로 누른 뒤에는 테두리를 그리지 않고, 키보드로 왔을 때만 그려
   초점이 어디 있는지 보인다(연결 띠 .skx-conn 과 같은 규칙. 전에는 늘 지워 키보드 사용자가 초점을 잃었다) */
.cm-block:focus {
  outline: none;
}
.cm-block:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.cm-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.cm-tag {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent, #7c4dff);
  background: var(--lilac, #f1edff);
  padding: 3px 10px;
  border-radius: 20px;
}
.cm-copy {
  padding: 5px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.cm-copy:hover {
  background: var(--lilac, #f1edff);
  border-color: var(--accent, #7c4dff);
  color: var(--accent, #7c4dff);
}
.cm-refs {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cm-ref-line {
  margin: 0;
  font-size: 12.5px;
  color: var(--ink);
  line-height: 1.6;
}
.cm-cite {
  margin: 0;
  font-size: 13px;
  color: var(--ink);
  line-height: 1.7;
}
.cm-loading {
  font-size: 13px;
  color: #bbb;
  margin: 0;
  text-align: center;
  padding: 12px;
}
.cm-modal-enter-active,
.cm-modal-leave-active {
  transition: opacity 0.2s;
}
.cm-modal-enter-from,
.cm-modal-leave-to {
  opacity: 0;
}
</style>
