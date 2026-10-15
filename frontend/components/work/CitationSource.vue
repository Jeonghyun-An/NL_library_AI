<!-- frontend/components/work/CitationSource.vue -->
<!-- 오른쪽 패널의 인용 근거 탭 본문(D24 A안) — 인용한 논문 카드 + 그 문장을 쓸 때 모델에 넘긴 원문 대목(가장 많이
     겹치는 문장을 강조) + [원문 보기] + [이 논문과 대화하기]. 조회·패널은 ProposalStep 이 쥐고 이 부품은 그리기만 한다 -->
<template>
  <div class="wk-cite">
    <section class="wk-cite__card" aria-label="인용한 논문">
      <p class="wk-cite__title">{{ head.title }}</p>
      <p v-if="head.byline" class="rs-muted wk-cite__byline">{{ head.byline }}</p>
      <blockquote class="wk-cite__quote"><span class="rs-sr-only">인용한 문장: </span>{{ quote }}</blockquote>
    </section>

    <p v-if="loading" class="rs-muted" role="status">원문 대목을 불러오는 중입니다</p>
    <p v-else-if="error" class="rs-alert" role="alert">{{ error }}</p>
    <section v-else-if="source?.excerpt" class="wk-cite__excerpt" aria-label="모델에 넘긴 원문 대목">
      <p class="wk-cite__heading">
        이 문장을 쓸 때 넘긴 원문 대목<span v-if="pageText" class="rs-muted"> · {{ pageText }}</span>
      </p>
      <p class="wk-cite__text">
        <template v-for="(part, i) in parts" :key="i">
          <mark v-if="part.mark" class="wk-cite__mark">{{ part.text }}</mark>
          <template v-else>{{ part.text }}</template>
        </template>
      </p>
      <p v-if="!marked" class="rs-muted">
        인용한 문장과 겹치는 대목 문장을 찾지 못했습니다 — 대목 전체를 그대로 보입니다.
      </p>
    </section>
    <section v-else-if="source" class="wk-cite__excerpt" aria-label="초록">
      <p class="wk-cite__heading">원문 대목을 읽지 못해 초록을 보입니다</p>
      <p class="wk-cite__text">{{ passageText(source.abstract) || "초록이 없습니다." }}</p>
    </section>
    <p v-else class="rs-muted">이 인용의 근거 기록을 찾지 못했습니다 — [원문 보기]로 논문을 직접 확인하세요.</p>

    <div class="wk-cite__actions">
      <button type="button" class="rs-btn rs-btn--small" @click="emit('open-pdf', pdfTarget)">원문 보기</button>
      <button type="button" class="rs-btn rs-btn--small rs-btn--ghost" @click="emit('chat')">이 논문과 대화하기</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { OpenPdfPayload } from "~/types/research";
import type { CitePick, PaperMeta, SectionSource } from "~/types/work";
import { citationPdfTarget, citedQuote, excerptParts } from "~/utils/citationEvidence";
import { panelHead } from "~/utils/deepRead";
import { passageText } from "~/utils/passageText";

const props = defineProps<{
  pick: CitePick;
  meta: PaperMeta | null;
  source: SectionSource | null;
  loading: boolean;
  error: string | null;
}>();
const emit = defineEmits<{ "open-pdf": [payload: OpenPdfPayload]; chat: [] }>();

const head = computed(() =>
  props.meta ? panelHead({ cntsId: props.pick.cntsId, meta: props.meta }) : { title: props.pick.cntsId, byline: "" },
);
// 인용한 문장 — 좁은 화면에서는 패널이 본문을 덮어 강조한 문장이 보이지 않아 이 카드가 그 문장을 읽는 자리다. 본문에 보이는
// 글 그대로 — [E#] 칩은 빼고 [F#] 는 그 절의 수치 값으로(ProposalSection 이 누를 때 만든 pick.quote, S4 quality 검토 반영 —
// 파트 S 메모 13). quote 가 없으면 수치 값을 몰라 [F#] 를 표기 그대로 둔다 — 지우면 '소장 논문 [F1]편' 이 '소장 논문편' 이 된다
const quote = computed(() => props.pick.quote ?? citedQuote(props.pick.sentence, []));
// 대목은 excerptParts 가 정리한 글(passageText — <br> 태그 글자를 줄바꿈으로)로 나누고 강조한다. 대목 고르기에는 마커가 든
// 원문(pick.sentence)을 넘긴다 — 받치는 말(citedClaims)을 [E#] 묶음으로 나눈다. 누른 칩의
// 근거 번호도 넘긴다 — 한 문장에 근거가 둘 이상이면 그 칩이 받치는 말로 고른다(S3 3차 검토 반영 — 파트 S 메모 12)
const parts = computed(() =>
  props.source?.excerpt ? excerptParts(props.source.excerpt.text, props.pick.sentence, props.pick.eid) : [],
);
// 겹치는 문장이 없으면(번역·요약해 쓴 문장 등) 강조 없이 대목 전체를 보이고 그렇다고 알린다
const marked = computed(() => parts.value.some((p) => p.mark));
// 대목이 없으면 논문을 처음부터 연다(citationPdfTarget). 근거 기록을 못 찾았을 때도 같다
const pdfTarget = computed<OpenPdfPayload>(() =>
  props.source ? citationPdfTarget(props.source, head.value.title) : { cntsId: props.pick.cntsId, title: head.value.title },
);
// 대목 이름은 뷰어와 같은 글(pageLabel — 'p.6–8'·'쪽 정보 없음')
const pageText = computed(() => (props.source?.excerpt ? (pdfTarget.value.passages?.[0]?.label ?? null) : null));
</script>
