<!-- frontend/components/research/ResearchLive.vue -->
<!-- 탐색 중 본문(보고서 자리)의 'AI가 지금 하는 일' — 맨 위에 지금 하는 일 한 줄(살아 있는 점), 숫자 칸, 재검색 알림, 그 아래
     하위질문마다 회차 단계(검색 → 자기점검 → 다시 찾기)가 생기는 대로 내려앉는다. 지금 도는 하위질문은 펼치고 검토 중인 논문 제목까지
     보이며, 끝난 하위질문은 한 줄 요약으로 접는다(눌러 펼침). 전에는 이 과정이 옆 칸에만 쌓여 본문에는 하위질문 자리만 보였다 —
     탐색 중에는 과정을 본문에 크게, 보고서를 쓰기 시작하면 과정(탐색 경로)은 다시 옆 칸으로 간다(사용자 결정 2026-10-14).
     하위질문 줄의 id 는 절 자리와 같다(slotElementId) — 따라가기(followTarget)가 도는 하위질문으로 옮긴다 -->
<template>
  <section class="rs-live" aria-labelledby="rs-live-title">
    <header class="rs-live__head">
      <h2 id="rs-live-title" class="rs-live__kicker"><span class="rs-live__dot" aria-hidden="true" />지금 AI가 하는 일</h2>
      <p class="rs-live__now" role="status" aria-live="polite">{{ nowLine }}</p>
    </header>

    <dl class="rs-live__counters">
      <div class="rs-live__counter">
        <dt>검토한 논문</dt>
        <dd :key="`r${view.counters.papersReviewed}`">{{ shown(view.counters.papersReviewed) }}</dd>
      </div>
      <div class="rs-live__counter">
        <dt>채택한 근거</dt>
        <dd :key="`a${view.counters.evidenceAdopted}`">{{ shown(view.counters.evidenceAdopted) }}</dd>
      </div>
      <div v-if="showsExcludedCounter(view)" class="rs-live__counter">
        <dt>제외</dt>
        <dd :key="`x${view.counters.excluded}`">{{ shown(view.counters.excluded) }}</dd>
      </div>
      <div class="rs-live__counter">
        <dt>재검색</dt>
        <dd :key="`c${view.counters.rechecks}`">{{ shown(view.counters.rechecks) }}</dd>
      </div>
    </dl>

    <ol class="rs-live__subqs">
      <li
        v-for="sq in view.subqs"
        :id="slotElementId(sq.idx)"
        :key="sq.idx"
        class="rs-live__subq"
        :class="[`is-${sq.status}`, { 'is-current': running?.idx === sq.idx }]"
      >
        <div class="rs-live__subq-head">
          <span class="rs-live__no" aria-hidden="true">{{ sq.status === "done" ? "✓" : sq.idx + 1 }}</span>
          <span class="rs-live__subq-title">
            <span class="rs-sr-only">하위질문 {{ sq.idx + 1 }}: </span>{{ sq.title }}
          </span>
          <span class="rs-live__subq-state">{{ stateLabel(sq) }}</span>
          <button
            v-if="collapsible(sq)"
            type="button"
            class="rs-live__toggle"
            :aria-expanded="isOpen(sq)"
            :aria-controls="stepsId(sq.idx)"
            @click="toggle(sq.idx)"
          >
            {{ isOpen(sq) ? "접기" : "과정 보기" }}
          </button>
        </div>

        <div v-if="isOpen(sq)" :id="stepsId(sq.idx)" class="rs-live__body">
          <!-- 재검색 알림 — 지금 도는 하위질문의 자기점검이 근거 부족을 내면 그 줄 안에 크게 -->
          <p v-if="highlightFor(sq)" class="rs-live__alert">
            <strong>근거 부족</strong> → ‘{{ highlightFor(sq)!.nextQuery }}’(으)로 다시 찾습니다
            <span v-if="highlightFor(sq)!.note" class="rs-live__alert-note">{{ highlightFor(sq)!.note }}</span>
          </p>
          <!-- 새 단계는 CSS 애니메이션으로 떠오른다(Vue 전환은 화면 프레임이 돌아야 끝나 숨은 탭에서 투명한 채로 남았다) -->
          <ol class="rs-live__steps">
            <li
              v-for="step in stepsOf(sq)"
              :key="step.key"
              class="rs-live__step"
              :class="[`is-${step.kind}`, step.tone && `is-${step.tone}`, { 'is-pending': step.pending }]"
            >
              <span class="rs-live__step-ico" aria-hidden="true">{{ iconOf(step) }}</span>
              <span class="rs-live__step-body">
                <span class="rs-live__step-title">{{ step.title }}</span>
                <span v-if="step.detail" class="rs-live__step-detail">{{ step.detail }}</span>
              </span>
            </li>
          </ol>
          <!-- 검토 중인 논문 — 후보 이벤트가 세운 이번 회차의 후보(점검이 끝나면 근거 장부로 떨어진다) -->
          <div v-if="running?.idx === sq.idx && sq.reviewing?.papers.length" class="rs-live__reviewing">
            <p class="rs-live__reviewing-title">검토 중인 논문 {{ sq.reviewing.papers.length }}편</p>
            <ul class="rs-live__papers">
              <li v-for="p in sq.reviewing.papers.slice(0, REVIEW_SHOWN)" :key="p.cntsId" class="rs-live__paper">
                {{ p.title || p.cntsId }}
              </li>
              <li v-if="sq.reviewing.papers.length > REVIEW_SHOWN" class="rs-live__paper is-more">
                외 {{ sq.reviewing.papers.length - REVIEW_SHOWN }}편
              </li>
            </ul>
          </div>
          <p v-if="sq.status === 'failed' && sq.error" class="rs-live__error">{{ sq.error }}</p>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { computed, shallowRef } from "vue";
import type { ResearchView, SubqView } from "~/types/research";
import { slotElementId } from "~/utils/planSlots";
import { showsExcludedCounter, subqStatusLabel } from "~/utils/researchEvents";
import { doneSummary, liveNowLine, liveRunning, roundSteps, type LiveStep } from "~/utils/researchLive";

const props = defineProps<{ view: ResearchView }>();

// 단계 앞 동그라미 안의 기호 — 검색 ⌕ · 점검(중 … · 충분 ✓ · 부족 !) · 다시 찾기 ↻
function iconOf(step: LiveStep): string {
  if (step.kind === "search") return "⌕";
  if (step.kind === "recheck") return "↻";
  if (step.pending) return "…";
  return step.tone === "ok" ? "✓" : step.tone === "warn" ? "!" : "·";
}
// 검토 중 후보는 몇 편만 제목을 보이고 나머지는 수로 — 전체는 옆 칸 근거 장부에 있다
const REVIEW_SHOWN = 4;

const running = computed(() => liveRunning(props.view.subqs));
const nowLine = computed(() => liveNowLine(props.view.subqs));

function shown(n: number | null): string {
  return n === null ? "—" : n.toLocaleString("ko-KR");
}

function stateLabel(sq: SubqView): string {
  return sq.status === "done" ? doneSummary(sq) : subqStatusLabel(sq);
}

function stepsOf(sq: SubqView): LiveStep[] {
  const last = sq.rounds[sq.rounds.length - 1];
  return sq.rounds.flatMap((r) => roundSteps(r, running.value?.idx === sq.idx && last?.round === r.round));
}

function highlightFor(sq: SubqView) {
  const h = props.view.highlight;
  return h && h.subqIdx === sq.idx && running.value?.idx === sq.idx ? h : null;
}

// 지금 도는 하위질문은 늘 펼친다. 끝난·멈춘 하위질문은 회차가 있으면 눌러 펼친다(대기 중인 것은 펼칠 것이 없다)
const opened = shallowRef(new Set<number>());

function collapsible(sq: SubqView): boolean {
  return running.value?.idx !== sq.idx && sq.rounds.length > 0;
}

function isOpen(sq: SubqView): boolean {
  if (running.value?.idx === sq.idx) return true;
  if (sq.status === "failed" && sq.error) return true;
  return opened.value.has(sq.idx);
}

function toggle(idx: number): void {
  const next = new Set(opened.value);
  if (!next.delete(idx)) next.add(idx);
  opened.value = next;
}

function stepsId(idx: number): string {
  return `rs-live-steps-${idx}`;
}
</script>
