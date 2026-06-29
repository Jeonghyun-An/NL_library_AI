<template>
  <div class="skx-app">
    <AppSidebar
      @cart="showToast('대출 장바구니 기능은 준비 중입니다.')"
      @save="showToast('저장목록 기능은 준비 중입니다.')"
    />

    <main class="skx-result">
      <h1 class="skx-sr-only">추천 도서 큐레이션 상세</h1>
      <div class="skx-result-card">
        <!-- 뒤로가기 -->
        <button type="button" class="skx-detail-back" @click="$router.back()">
          <img class="skx-detail-back__icon" src="/img/ico-arrow.svg" alt="" />
          <span class="skx-detail-back__label">돌아가기</span>
        </button>

        <!-- 히어로 배너 -->
        <div :class="['skx-rcd-hero', `skx-rcd-hero--${scenario.heroType}`]">
          <template v-if="scenario.heroType === '02'">
            <span class="skx-mt-deco skx-mt-deco--1" aria-hidden="true"
              ><i></i
            ></span>
            <span class="skx-mt-deco skx-mt-deco--2" aria-hidden="true"
              ><i></i
            ></span>
            <span class="skx-mt-deco skx-mt-deco--3" aria-hidden="true"
              ><i></i
            ></span>
          </template>
          <template v-if="scenario.heroType === '03'">
            <img
              class="skx-reco-c03 skx-reco-c03--star-s"
              src="/img/skx-reco-c03-star.svg"
              alt=""
              aria-hidden="true"
            />
            <img
              class="skx-reco-c03 skx-reco-c03--star-l"
              src="/img/skx-reco-c03-star.svg"
              alt=""
              aria-hidden="true"
            />
            <img
              class="skx-reco-c03 skx-reco-c03--curve"
              src="/img/skx-reco-c03-curve.svg"
              alt=""
              aria-hidden="true"
            />
          </template>
          <div class="skx-rcd-hero__body">
            <h2 class="skx-rcd-hero__tit" v-html="scenario.title"></h2>
            <p class="skx-rcd-hero__sub">{{ scenario.sub }}</p>
          </div>
        </div>

        <!-- AI 텍스트 (타이핑 애니메이션) -->
        <div class="skx-rcd-ai">
          <div class="skx-rcd-ai__top">
            <img
              class="skx-rcd-ai__logo"
              src="/img/logo-mark.svg"
              alt="SKOVIX AI"
            />
            <span class="skx-rcd-ai__label">{{ scenario.aiLabel }}</span>
          </div>
          <div
            :class="['skx-ai-answer-wrap', aiExpanded && 'is-expanded']"
            ref="aiWrapRef"
          >
            <div class="skx-ai-answer">
              <p class="skx-ai-answer__text">{{ typedLine1 }}</p>
              <p class="skx-ai-answer__text">{{ typedLine2 }}</p>
            </div>
            <button
              v-if="showExpandBtn || typingDone"
              type="button"
              class="skx-ai-expand-bar"
              :aria-expanded="aiExpanded"
              @click="toggleAiExpand"
            >
              <span class="skx-ai-expand-bar__label">{{
                aiExpanded ? "접기" : "펼치기"
              }}</span>
              <img
                class="skx-ai-expand-bar__arrow"
                src="/img/ico-arrow.svg"
                alt=""
                aria-hidden="true"
                :style="
                  aiExpanded
                    ? 'transform:rotate(90deg)'
                    : 'transform:rotate(-90deg)'
                "
              />
            </button>
          </div>
        </div>

        <!-- 도서 선택 -->
        <div class="skx-rcd-select">
          <h3 class="skx-rcd-select__tit">
            가장 나에게 도움이되는 책을 선택해주세요.
          </h3>
          <div class="skx-rcd-book-grid">
            <button
              v-for="(book, i) in scenario.books"
              :key="i"
              type="button"
              :class="['skx-rcd-book-card', `skx-rcd-book-card--${i + 1}`]"
              @click="openModal(book)"
            >
              <div class="skx-rcd-book-card__head">
                <img
                  class="skx-rcd-book-card__icon"
                  src="/img/ico-book-select.svg"
                  alt=""
                />
                <p class="skx-rcd-book-card__desc" v-html="book.desc"></p>
              </div>
              <div class="skx-rcd-book-card__cover">
                <img :src="book.cover" :alt="book.name" />
              </div>
              <p class="skx-rcd-book-card__name">{{ book.name }}</p>
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- 맞춤도서 추천 팝업 -->
    <div
      v-if="modalOpen"
      class="skx-rcd-modal-overlay"
      role="dialog"
      aria-modal="true"
      @click.self="modalOpen = false"
    >
      <div class="skx-rcd-modal">
        <button
          type="button"
          class="skx-rcd-modal__close"
          aria-label="닫기"
          @click="modalOpen = false"
        >
          <img src="/img/ico-close.svg" alt="" />
        </button>
        <h2 class="skx-rcd-modal__title">맞춤도서 추천</h2>
        <div class="skx-rcd-modal__card">
          <div class="skx-rcd-modal__card-top">
            <span class="skx-rcd-modal__badge">Book solution</span>
            <p class="skx-rcd-modal__desc" v-html="selectedBook?.desc"></p>
          </div>
          <div class="skx-rcd-modal__cover">
            <img :src="selectedBook?.cover" :alt="selectedBook?.name" />
          </div>
          <div class="skx-rcd-modal__book-info">
            <p class="skx-rcd-modal__book-title">{{ selectedBook?.name }}</p>
          </div>
        </div>
        <div class="skx-rcd-modal__btns">
          <button
            type="button"
            class="skx-rcd-modal__btn skx-rcd-modal__btn--outline"
          >
            <img src="/img/ico-share.svg" alt="" />솔루션 보내기
          </button>
          <button
            type="button"
            class="skx-rcd-modal__btn skx-rcd-modal__btn--dark"
          >
            <img src="/img/ico-download.svg" alt="" />솔루션 저장하기
          </button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <Transition name="skx-toast">
        <div v-if="toast" class="skx-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
const route = useRoute();
const scenarioId = String(route.params.id ?? "02");

const toast = ref("");
function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

interface ScenarioBook {
  name: string;
  desc: string;
  cover: string;
}

interface Scenario {
  heroType: string;
  title: string;
  sub: string;
  aiLabel: string;
  aiLines: [string, string];
  books: ScenarioBook[];
}

const SCENARIOS: Record<string, Scenario> = {
  "01": {
    heroType: "01",
    title: "위로가 필요할 때",
    sub: "지친 마음에 따뜻한 위로가 필요하다면 이 책들을 펼쳐보세요!",
    aiLabel: "위로가 필요한 당신을 위해 AI가 추천하는 책!",
    aiLines: [
      "위로가 필요한 당신을 위한 책들입니다.",
      "마음의 상처를 치유해 줄 따뜻한 이야기들을 골랐습니다.",
    ],
    books: [
      {
        name: "강아지똥",
        desc: "보잘것없는 존재도<br>소중한 가치가 있음을",
        cover: "/img/img-book-01.jpg",
      },
      {
        name: "알사탕",
        desc: "자신의 마음을<br>경청하는 법",
        cover: "/img/img-book-alsatang.jpg",
      },
      {
        name: "구름빵",
        desc: "상상력과 따뜻함이<br>가득한 이야기",
        cover: "/img/img-book-02.jpg",
      },
      {
        name: "솔이의 추석 이야기",
        desc: "가족과 함께하는<br>따뜻한 명절",
        cover: "/img/img-book-01.jpg",
      },
    ],
  },
  "02": {
    heroType: "02",
    title: "심리적 단단함이 필요할 때",
    sub: "마음 근육을 키워 단단해지고 싶다면 이 책들을 읽어보세요!",
    aiLabel: "심리적 단단함을 만들 수 있게 AI가 추천하는 책!",
    aiLines: [
      "심리적 단단함을 만들 수 있게 AI가 추천하는 책!",
      "추천 도서들은 고난과 역경 속에서도 흔들리지 않는 내면의 중심을 잡았던 이들의 지혜가 담겨 있어, 무너진 기강을 세우고 삶의 맷집을 키워주는 도서들입니다.",
    ],
    books: [
      {
        name: "다산 정약용 산문집",
        desc: "유배지의 절망 속에서 피려낸<br>명철한 통찰로, 내면의 기강 바로잡기",
        cover: "/img/rcd-book-01.png",
      },
      {
        name: "너는 가능성이다",
        desc: "인간 본연의 숭고한 가치와 가능성을<br>깨워 주어, 무기력증 깨부수기",
        cover: "/img/rcd-book-02.png",
      },
      {
        name: "혼자 일어설 때 햇살은 더욱 눈부시다",
        desc: "홀로서기의 당당함과 회복탄력성을<br>전해주며 용기를 주는 책",
        cover: "/img/rcd-book-03.png",
      },
      {
        name: "방황하는 내국인",
        desc: "유배지의 절망 속에서 피려낸<br>명철한 통찰로, 내면의 기강 바로잡기",
        cover: "/img/rcd-book-04.png",
      },
    ],
  },
  "03": {
    heroType: "03",
    title: "늦은 밤, 잠이 오지 않을 때",
    sub: "잠 못 드는 밤, 마음을 가라앉혀 줄 책들을 골라봤어요!",
    aiLabel: "잠 못 드는 밤을 위해 AI가 추천하는 책!",
    aiLines: [
      "잠 못 드는 밤을 위한 책들입니다.",
      "마음을 차분히 가라앉혀 줄 이야기들을 골랐습니다.",
    ],
    books: [
      {
        name: "강아지똥",
        desc: "보잘것없는 존재도<br>소중한 가치가 있음을",
        cover: "/img/img-book-01.jpg",
      },
      {
        name: "알사탕",
        desc: "자신의 마음을<br>경청하는 법",
        cover: "/img/img-book-alsatang.jpg",
      },
      {
        name: "구름빵",
        desc: "상상력과 따뜻함이<br>가득한 이야기",
        cover: "/img/img-book-02.jpg",
      },
      {
        name: "솔이의 추석 이야기",
        desc: "가족과 함께하는<br>따뜻한 명절",
        cover: "/img/img-book-01.jpg",
      },
    ],
  },
  "04": {
    heroType: "04",
    title: "흥미진진한 역사 이야기가 궁금할 때",
    sub: "흥미진진한 역사의 세계로 빠져들 책들을 추천해드려요!",
    aiLabel: "역사가 궁금한 당신을 위해 AI가 추천하는 책!",
    aiLines: [
      "역사에 대한 흥미를 키워줄 책들입니다.",
      "생생한 역사 이야기를 담은 도서들을 선별했습니다.",
    ],
    books: [
      {
        name: "강아지똥",
        desc: "보잘것없는 존재도<br>소중한 가치가 있음을",
        cover: "/img/img-book-01.jpg",
      },
      {
        name: "알사탕",
        desc: "자신의 마음을<br>경청하는 법",
        cover: "/img/img-book-alsatang.jpg",
      },
      {
        name: "구름빵",
        desc: "상상력과 따뜻함이<br>가득한 이야기",
        cover: "/img/img-book-02.jpg",
      },
      {
        name: "방황하는 내국인",
        desc: "유배지의 절망 속에서<br>명철한 통찰",
        cover: "/img/rcd-book-04.png",
      },
    ],
  },
};

const scenario = computed<Scenario>(
  () => (SCENARIOS[scenarioId] || SCENARIOS["02"]) as Scenario,
);

// AI typing animation
const typedLine1 = ref("");
const typedLine2 = ref("");
const aiWrapRef = ref<HTMLElement | null>(null);
const aiExpanded = ref(false);
const showExpandBtn = ref(false);
const typingDone = ref(false);

function toggleAiExpand() {
  if (!typingDone.value) {
    typedLine1.value = scenario.value.aiLines[0];
    typedLine2.value = scenario.value.aiLines[1];
    typingDone.value = true;
  }
  aiExpanded.value = !aiExpanded.value;
}

function typeLine(lineRef: Ref<string>, text: string, onDone?: () => void) {
  let i = 0;
  const tick = () => {
    if (i < text.length) {
      lineRef.value += text[i++];
      setTimeout(tick, 28);
    } else {
      onDone?.();
    }
  };
  tick();
}

// Modal
const modalOpen = ref(false);
const selectedBook = ref<ScenarioBook | null>(null);

function openModal(book: ScenarioBook) {
  selectedBook.value = book;
  modalOpen.value = true;
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") modalOpen.value = false;
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  setTimeout(() => {
    typeLine(typedLine1, scenario.value.aiLines[0], () => {
      setTimeout(() => {
        typeLine(typedLine2, scenario.value.aiLines[1], () => {
          typingDone.value = true;
          nextTick(() => {
            if (
              aiWrapRef.value &&
              aiWrapRef.value.scrollHeight > aiWrapRef.value.clientHeight + 10
            ) {
              showExpandBtn.value = true;
            }
          });
        });
      }, 120);
    });
  }, 400);
});

onUnmounted(() => {
  document.removeEventListener("keydown", onKeydown);
});
</script>
