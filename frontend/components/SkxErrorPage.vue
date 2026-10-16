<!-- frontend/components/SkxErrorPage.vue -->
<!-- 전역 오류 화면의 본문 — 없는 주소(404)와 화면을 그리다 난 치명 오류. error.vue 가 이것을 그리고, 오류 화면 모음(/dev/error-states)이
     preview 로 같은 것을 액자에 담는다(복제 마크업 없이 — 디자인을 고치면 둘이 함께 바뀐다).
     error.vue 는 app.vue 대신 통째로 그려지므로 홀로그램 배경을 여기 다시 둔다(사이드바가 없어 그 폭을 가리는 veil 은 두지 않는다).
     오류 객체의 영문 message·stack 은 받지도 보이지도 않는다 — 상태 코드만 받는다. 문구는 utils/apiErrors.ts 의 ERROR_PAGE_TEXT.
     preview:
       - 버튼이 이동·새로고침을 하지 않는다(모음 안에서 눌러도 화면이 바뀌지 않게)
       - <main>·<h1> 대신 <div>·<p> — 모음 페이지의 랜드마크·제목 줄과 겹치지 않게(모양은 클래스가 정해 같다)
       - .skx-error-page--preview 로 화면 높이(100vh) 대신 부모(액자) 높이를 채운다
       - 홀로그램(.skx-holo)은 position: fixed 라 액자 쪽에 transform + overflow: hidden 을 둬야 배경이 액자 밖으로 새지 않는다
     디자인 훅(style_skovix.css '[S] 공통 오류·빈 상태'): .skx-error-page · .skx-error-page--preview · [data-status] · .skx-error-page__main · .skx-error-page__logo
       · 안의 상태 블록은 .skx-error-page .skx-state -->
<template>
  <div class="skx-error-page" :class="{ 'skx-error-page--preview': preview }" :data-status="status">
    <div class="skx-holo" aria-hidden="true">
      <span class="skx-holo__band skx-holo__band--1"></span>
      <span class="skx-holo__band skx-holo__band--2"></span>
      <span class="skx-holo__band skx-holo__band--3"></span>
    </div>
    <component :is="preview ? 'div' : 'main'" class="skx-error-page__main">
      <SkovixWordmark class="skx-error-page__logo" decorative />
      <SkxErrorState
        v-if="notFound"
        kind="notFound"
        :title-tag="titleTag"
        :title="ERROR_PAGE_TEXT.notFound.title"
        :message="ERROR_PAGE_TEXT.notFound.message"
      >
        <button type="button" class="skx-state__action" @click="goHome">{{ ERROR_PAGE_TEXT.home }}</button>
      </SkxErrorState>
      <SkxErrorState
        v-else
        kind="error"
        :title-tag="titleTag"
        :title="ERROR_PAGE_TEXT.fatal.title"
        :message="ERROR_PAGE_TEXT.fatal.message"
        @retry="reload"
      >
        <button type="button" class="skx-state__action" @click="goHome">{{ ERROR_PAGE_TEXT.home }}</button>
      </SkxErrorState>
    </component>
  </div>
</template>

<script setup lang="ts">
import { ERROR_PAGE_TEXT } from "~/utils/apiErrors";

const props = withDefaults(
  defineProps<{
    /** HTTP 상태 — 404 면 '찾을 수 없음', 그 밖은 치명 오류 */
    status: number;
    /** 오류 화면 모음의 액자 안 — 버튼이 아무 데도 가지 않고, 랜드마크·제목 요소를 쓰지 않는다 */
    preview?: boolean;
  }>(),
  { preview: false },
);

const notFound = computed(() => props.status === 404);
const titleTag = computed(() => (props.preview ? "p" : "h1"));

/** 오류를 걷고 처음 화면으로 */
function goHome(): void {
  if (props.preview) return;
  clearError({ redirect: "/" });
}

/** 지금 주소를 새로 불러온다 — 화면 상태가 꼬여 난 오류일 수 있어 앱을 처음부터 다시 띄운다 */
function reload(): void {
  if (props.preview) return;
  window.location.reload();
}
</script>
