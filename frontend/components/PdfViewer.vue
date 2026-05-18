<template>
  <Teleport to="body">
    <div class="pdf-overlay" @click.self="$emit('close')">
      <div class="pdf-modal">

        <div class="pdf-header">
          <span class="pdf-title" :title="title">{{ title }}</span>
          <button class="close-btn" @click="$emit('close')">✕</button>
        </div>

        <iframe
          class="pdf-frame"
          :src="viewerUrl"
          allowfullscreen
        />

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

const viewerUrl = computed(() => {
  const file = encodeURIComponent(`/api/books/${props.cntsId}/pdf`);
  return `/pdfjs/web/viewer.html?file=${file}`;
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

.pdf-frame {
  flex: 1;
  width: 100%;
  border: none;
}
</style>
