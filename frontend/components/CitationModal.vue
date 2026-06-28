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

            <div v-if="loading" class="cm-loading">불러오는 중...</div>

            <template v-else>
              <!-- 참고문헌 (extra.references 목록 전체) -->
              <div class="cm-block">
                <div class="cm-block-head">
                  <span class="cm-tag">참고문헌</span>
                  <button class="cm-copy" @click="copyRefs">
                    {{ copied === "refs" ? "✓ 복사됨" : "복사" }}
                  </button>
                </div>
                <div v-if="references.length" class="cm-refs">
                  <p
                    v-for="(ref, i) in references"
                    :key="i"
                    class="cm-ref-line"
                  >
                    {{ ref }}
                  </p>
                </div>
                <p v-else class="cm-empty">참고문헌 정보가 없습니다.</p>
              </div>

              <!-- 인용 (전체 인용문 · 국문/영문 토글) -->
              <div class="cm-block">
                <div class="cm-block-head">
                  <span class="cm-tag">인용</span>
                  <button class="cm-copy" @click="copyCite">
                    {{ copied === "cite" ? "✓ 복사됨" : "복사" }}
                  </button>
                </div>
                <p class="cm-cite">{{ citeText || "인용 정보가 없습니다." }}</p>
              </div>
            </template>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
const props = defineProps<{
  open: boolean;
  bookId: string | null;
  references: string[];
}>();
defineEmits<{ (e: "close"): void }>();

const config = useRuntimeConfig();
const apiBase = (config.public.apiBase as string) || "";

const citeStyle = ref<"APA">("APA");
const lang = ref<"ko" | "en">("ko");
const citation = ref<{ korean: string; english: string } | null>(null);
const loading = ref(false);
const copied = ref<"" | "refs" | "cite">("");

const citeText = computed(() =>
  !citation.value
    ? ""
    : lang.value === "ko"
      ? citation.value.korean
      : citation.value.english,
);

async function loadCitation() {
  if (!props.bookId) return;
  loading.value = true;
  citation.value = null;
  copied.value = "";
  try {
    citation.value = await $fetch<{ korean: string; english: string }>(
      `${apiBase}/papers/${props.bookId}/citation`,
    );
  } catch {
    citation.value = {
      korean: "인용 정보를 불러오지 못했습니다.",
      english: "",
    };
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.open, props.bookId] as const,
  ([isOpen]) => {
    if (isOpen && props.bookId) loadCitation();
  },
  { immediate: true },
);

async function copyText(text: string, key: "refs" | "cite") {
  if (!text) return;
  await navigator.clipboard.writeText(text);
  copied.value = key;
  setTimeout(() => (copied.value = ""), 2000);
}
function copyRefs() {
  copyText(props.references.join("\n"), "refs");
}
function copyCite() {
  copyText(citeText.value, "cite");
}
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
.cm-empty,
.cm-loading {
  font-size: 13px;
  color: #bbb;
  margin: 0;
}
.cm-loading {
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
