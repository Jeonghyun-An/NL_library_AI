<template>
  <div class="search-input-wrap" :class="{ focused }">
    <textarea
      ref="textareaRef"
      v-model="query"
      :placeholder="placeholder"
      :disabled="disabled"
      rows="1"
      @focus="focused = true"
      @blur="focused = false"
      @keydown="handleKeydown"
      @input="autoResize"
    />
    <div class="btn-area">
      <button
        class="send-btn"
        :disabled="!query.trim() || disabled"
        @click="submit"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M22 2L11 13" />
          <path d="M22 2L15 22L11 13L2 9L22 2Z" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  placeholder?: string;
  disabled?: boolean;
  modelValue?: string;
}>();

const emit = defineEmits<{
  submit: [query: string];
  "update:modelValue": [value: string];
}>();

const query = ref(props.modelValue || "");
const focused = ref(false);
const textareaRef = ref<HTMLTextAreaElement>();

const MAX_HEIGHT = 200;

watch(
  () => props.modelValue,
  (v) => {
    if (v !== undefined) query.value = v;
  },
);
watch(query, (v) => emit("update:modelValue", v));

function handleKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submit();
  }
}

function submit() {
  const q = query.value.trim();
  if (!q) return;
  emit("submit", q);
}

function autoResize() {
  const el = textareaRef.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, MAX_HEIGHT) + "px";
  el.style.overflowY = el.scrollHeight > MAX_HEIGHT ? "auto" : "hidden";
}

onMounted(() => autoResize());
</script>

<style scoped>
.search-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border: 1px solid #d4d4d8; /* zinc-300 */
  border-radius: 14px;
  background: #f4f4f5; /* zinc-100 */
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
  width: 100%;
  max-width: 720px;
}

.search-input-wrap.focused {
  box-shadow: 0 0 0 2px rgba(161, 161, 170, 0.15);
}

textarea {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  font-size: 15px;
  line-height: 24px;
  font-family: inherit;
  background: transparent;
  overflow-y: hidden;
  min-height: 24px;
  padding: 6px 0;
  color: #18181b; /* zinc-900 */
}

textarea::placeholder {
  color: #a1a1aa; /* zinc-400 */
}

textarea:disabled {
  color: #71717a; /* zinc-500 */
}

.btn-area {
  flex-shrink: 0;
  align-self: flex-end;
}

.send-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: none;
  background: #1e293b; /* slate-800 */
  color: #f4f4f5; /* zinc-100 */
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
  margin: 4px 0;
}

.send-btn:hover:not(:disabled) {
  background: #334155; /* slate-700 */
}

.send-btn:disabled {
  background: #d4d4d8; /* zinc-300 */
  color: #a1a1aa; /* zinc-400 */
  cursor: not-allowed;
}

/* 스크롤바 */
textarea::-webkit-scrollbar {
  width: 4px;
}

textarea::-webkit-scrollbar-track {
  background: transparent;
}

textarea::-webkit-scrollbar-thumb {
  background: #d4d4d8; /* zinc-400 */
  border-radius: 2px;
}
</style>
