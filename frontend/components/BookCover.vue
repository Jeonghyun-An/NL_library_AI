<template>
  <div class="book-cover" :class="size">
    <img
      v-if="!imgError"
      :src="`/api/books/${bookId}/thumbnail`"
      :alt="bookId"
      class="cover-img"
      @error="imgError = true"
    />
    <div v-else class="placeholder">
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="#94a3b8"
        stroke-width="1.5"
      >
        <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
      </svg>
      <span class="placeholder-text">표지</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  bookId: string;
  size?: "small" | "large";
}>();

const imgError = ref(false);
</script>

<style scoped>
.book-cover {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #f1f5f9;
}

.book-cover.large {
  max-width: 180px;
  aspect-ratio: 3 / 4;
}

.book-cover.small {
  width: 100%;
  aspect-ratio: 3 / 4;
}

.cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  border-radius: 8px;
}

.placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.placeholder-text {
  font-size: 12px;
  color: #94a3b8;
}
</style>
