<!-- frontend/components/AppSidebar.vue -->
<template>
  <!-- 좁은 화면(≤768px) 전용 [사이드바 열기] — 사이드바는 본문을 밀지 않는 서랍(position: fixed, 왼쪽에서 열림)이라 본문 위 한 줄에 둔다.
       서랍이 닫히면 초점이 여기로 돌아온다. 넓은 화면에서는 CSS 로 숨는다(그쪽은 아래 접힌 띠가 한다) -->
  <button
    ref="openerBtn"
    type="button"
    class="skx-lnb-opener"
    aria-label="사이드바 열기"
    :aria-expanded="drawerOpen"
    aria-controls="skx-lnb"
    @click="openDrawer"
  >
    <img src="/img/ico-collapse.svg" alt="" />
  </button>
  <aside
    id="skx-lnb"
    ref="asideEl"
    :class="['skx-lnb', isCollapsed && 'is-lnb-collapsed', drawerOpen && 'is-drawer-open']"
    @keydown="onAsideKeydown"
  >
    <!-- 접힌 띠(데스크톱) — 위에서부터 [사이드바 열기](접기 버튼과 같은 아이콘) · [새 검색] · [DeepResearch].
         이름표는 마우스를 올리거나 키보드 초점이 갈 때 오른쪽에 뜨고 Esc 로 닫힌다. 좁은 화면(≤768px)에는 띠가 없다 — 위 [사이드바 열기]와 서랍이 대신한다.
         06e R6(사이드바 접기)는 이 띠 위에 붙인다 — 접힘 상태는 아래 open 이 정한다 -->
    <div class="skx-lnb__rail">
      <div class="skx-rail__item">
        <button
          type="button"
          class="skx-rail__btn skx-rail__btn--open"
          :aria-label="RAIL_TIPS.open"
          @click="expandFromRail"
          @pointerenter="showTip('open', $event)"
          @pointerleave="hideTip('open')"
          @focus="showTip('open', $event)"
          @blur="hideTip('open')"
        >
          <img class="skx-rail__ico" src="/img/ico-collapse.svg" alt="" />
        </button>
        <span v-if="railTip === 'open'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.open }}</span>
      </div>
      <!-- [새 검색] — 10-14 에 숨겼다가 DeepResearch 머리의 [연구 시작하기]가 작은 알약이 되어 겹침이 줄어 되살린다(사용자 결정 2026-10-15) -->
      <div class="skx-rail__item skx-rail__item--extra">
        <button
          type="button"
          class="skx-rail__btn"
          :aria-label="RAIL_TIPS.new"
          @click="newSearch"
          @pointerenter="showTip('new', $event)"
          @pointerleave="hideTip('new')"
          @focus="showTip('new', $event)"
          @blur="hideTip('new')"
        >
          <img class="skx-rail__ico" src="/img/ico-newchat.svg" alt="" />
        </button>
        <span v-if="railTip === 'new'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.new }}</span>
      </div>
      <div class="skx-rail__item skx-rail__item--extra">
        <button
          type="button"
          class="skx-rail__btn"
          :aria-label="RAIL_TIPS.research"
          :aria-describedby="researchActive ? 'skx-rail-live' : undefined"
          @click="openResearchFromRail"
          @pointerenter="showTip('research', $event)"
          @pointerleave="hideTip('research')"
          @focus="showTip('research', $event)"
          @blur="hideTip('research')"
        >
          <img class="skx-rail__ico" src="/img/ico-microscope.svg" alt="" />
          <span v-if="researchActive" class="skx-rail__dot" aria-hidden="true"></span>
        </button>
        <span v-if="researchActive" id="skx-rail-live" class="skx-sr-only">진행 중이거나 승인을 기다리는 연구가 있어요</span>
        <span v-if="railTip === 'research'" class="skx-rail__tip" aria-hidden="true">{{ RAIL_TIPS.research }}</span>
      </div>
    </div>

    <!-- 로고 + 접기 버튼 -->
    <div class="skx-lnb__logo">
      <a ref="homeLink" class="skx-logo" href="/" aria-label="SKOVIX 메인으로 이동">
        <SkovixWordmark class="skx-logo__word" />
      </a>
      <button
        ref="collapseBtn"
        type="button"
        class="skx-icon-btn"
        aria-label="사이드바 접기"
        @click="collapse"
      >
        <img src="/img/ico-collapse.svg" alt="" />
      </button>
    </div>

    <!-- 새 검색 — 랜딩 첫 화면으로(10-14 숨김 → 10-15 되살림, 사용자 결정) -->
    <div class="skx-lnb__new">
      <button ref="newSearchBtn" type="button" class="skx-newchat" @click="newSearch">
        <span class="skx-newchat__icon"><img src="/img/ico-newchat.svg" alt="" /></span>
        <span class="skx-newchat__label">새 검색</span>
      </button>
    </div>

    <!-- 메뉴 -->
    <nav v-if="SHOW_MOCKS" class="skx-lnb__menu" aria-label="주요 메뉴">
      <!-- <button type="button" class="skx-menu-item" @click="emit('cart')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-cart-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">대출 장바구니</span>
      </button> -->
      <button type="button" class="skx-menu-item" @click="emit('save')">
        <span class="skx-menu-item__icon"
          ><img src="/img/ico-bookmark-menu.svg" alt=""
        /></span>
        <span class="skx-menu-item__label">저장목록</span>
      </button>
    </nav>

    <!-- 검색기록 — 딥리서치 묶음 · 최근 검색(소장자료·논문 섞어 최신순) -->
    <div class="skx-history">
      <div class="skx-history__body">
        <!-- 첫 로드가 끝나기 전의 빈 목록을 '기록 없음'으로 보이지 않게 loaded 를 기다린다 -->
        <ClientOnly>
          <template v-if="loaded">
            <!-- 딥리드: 이 브라우저에서 나눈 자료별 대화(utils/deepReadHistory — 서버 기록과 따로). 대화가 있을 때만 보인다.
                 누르면 그 자료의 상세 화면이 딥리드 창을 연 채로 열리고 대화가 이어 보인다(대표 요청 2026-10-26 — 딥리드를 더 드러내게).
                 DeepResearch 와 같은 카드 — 머리를 누르면 머리 한 줄로 접히고(대화 수 칩), 펼치면 최근 3개 + '이전 대화 [n]'(사용자 2026-10-26) -->
            <section
              v-if="deepReadRows.length"
              class="skx-history__group skx-history__group--deepread"
              aria-labelledby="skx-history-deepread"
            >
              <div class="skx-history__head">
                <h2 id="skx-history-deepread" class="skx-history__title" tabindex="-1">
                  <button
                    type="button"
                    class="skx-history__fold"
                    :aria-expanded="!fold.deepread"
                    @click="toggleFold('deepread')"
                  >
                    {{ DEEP_READ }}
                    <span v-if="fold.deepread" class="skx-history-chip">{{ deepReadTotal }}</span>
                  </button>
                </h2>
              </div>
              <template v-if="!fold.deepread">
              <ul class="skx-history__list">
                <li v-for="d in deepReadRows" :key="d.id" class="skx-history__row">
                  <div class="skx-history__row-main">
                    <button
                      type="button"
                      :class="['skx-history-item', isDeepReadActive(d) && 'is-active']"
                      :aria-current="isDeepReadActive(d) ? 'page' : undefined"
                      @click="goDeepRead(d)"
                    >
                      <span class="skx-history-item__query" :title="firstQuestion(d)">{{ d.title }}</span>
                      <span class="skx-history-item__meta">
                        <span class="skx-history-badge is-done">{{ d.kind === "paper" ? "논문" : "소장자료" }}</span>
                        <span class="skx-history-item__time">질문 {{ questionCount(d) }}개 · {{ formatHistoryTime(d.updatedAt) }}</span>
                      </span>
                    </button>
                    <button
                      type="button"
                      class="skx-history-item__del"
                      :aria-label="`'${d.title}' 대화 기록 삭제`"
                      @click="deepRead.remove(d.id)"
                    >
                      <img src="/img/ico-delete.svg" alt="" />
                    </button>
                  </div>
                </li>
              </ul>
              <button
                v-if="deepReadHiddenCount > 0 || deepReadExpanded"
                type="button"
                :class="['skx-history__older', deepReadExpanded && 'is-expanded']"
                :aria-expanded="deepReadExpanded"
                :aria-label="olderDeepRead.ariaLabel"
                @click="deepReadExpanded = !deepReadExpanded"
              >
                <span>{{ olderDeepRead.label }}</span>
                <span v-if="olderDeepRead.count !== null" class="skx-history-chip" aria-hidden="true">{{ olderDeepRead.count }}</span>
                <svg class="skx-history__older-chev" viewBox="0 0 8 5" aria-hidden="true" focusable="false">
                  <path
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                    d="M7.86768 0.102681C8.03189 0.250461 8.0452 0.503377 7.89742 0.667584L4.29757 4.66758C4.22172 4.75187 4.11365 4.8 4.00026 4.8C3.88686 4.80001 3.7788 4.75188 3.70294 4.6676L0.102695 0.667599C-0.0450944 0.5034 -0.0317915 0.250484 0.132408 0.102695C0.296607 -0.0450943 0.549523 -0.0317915 0.697312 0.132408L4.00023 3.80207L7.30278 0.132424C7.45056 -0.0317831 7.70347 -0.0450996 7.86768 0.102681Z"
                  />
                </svg>
              </button>
              </template>
            </section>

            <!-- 딥리서치: 진행 중·승인 대기가 위로, 그다음 최신순. 머리는 'DeepResearch' · 오른쪽 '전체 삭제'(아래 '최근 검색' 머리와 같은 꼴).
                 묶음은 기록이 없어도 늘 보이고, 연구 기록이 하나도 없을 때만 머리 아래에 [연구 시작하기 >]를 둔다 — 기록이 있으면
                 버튼 없이 목록만(사용자 결정 2026-10-16). 기록이 있으면 머리를 눌러 머리 한 줄로 접는다 — 빈 묶음의 [연구 시작하기]처럼
                 작게(기록 수 칩, 진행 중·승인 대기가 있으면 점). 펼치면 3줄 + '이전 연구 [n]'(사용자 2026-10-26) -->
            <section class="skx-history__group skx-history__group--research" aria-labelledby="skx-history-research">
              <div class="skx-history__head">
                <div class="skx-history__head-main">
                  <h2 id="skx-history-research" class="skx-history__title" tabindex="-1">
                    <button
                      v-if="researchRows.length"
                      type="button"
                      class="skx-history__fold"
                      :aria-expanded="!researchFolded"
                      @click="toggleFold('research')"
                    >
                      {{ DEEP_RESEARCH }}
                      <span v-if="researchFolded" class="skx-history-chip">{{ groups.researchTotal }}</span>
                      <span v-if="researchFolded && researchActive" class="skx-history__fold-dot" aria-hidden="true"></span>
                    </button>
                    <template v-else>{{ DEEP_RESEARCH }}</template>
                  </h2>
                  <!-- '진행 중 N' 알약은 뺐다 — 진행 중인 줄의 '~ 중' 라벨이 산호 알약이라 같은 말이 겹쳤다(사용자 결정 2026-10-16).
                       화면 읽기 프로그램에는 묶음 머리에서 바로 들리게 글로만 남긴다 -->
                  <span v-if="liveCount > 0" class="skx-sr-only">진행 중 {{ liveCount }}</span>
                </div>
                <button
                  v-if="researchRows.length && !researchFolded"
                  ref="researchClearBtn"
                  type="button"
                  class="skx-history__clear"
                  @click="openConfirm('research')"
                >
                  전체 삭제
                </button>
              </div>
              <!-- 목록을 못 읽었으면(서버 거절·서버에 닿지 못했는데 이 브라우저의 사본도 빔) [연구 시작하기] 대신 줄 안내 + [다시 시도] —
                   기록이 없는 것처럼 보이지 않게. 앞서 읽은 줄이 있으면 그 줄은 그대로 두고 안내만 얹는다.
                   사이드바는 페이지마다 새로 그려져 같은 실패가 화면을 옮길 때마다 다시 나온다 — alert 면 낭독기가 하던 말을 끊고
                   거듭 읽으므로 status(차분한 알림)로 둔다(아래 최근 검색·저장 차단 줄도 같다) -->
              <SkxInlineError
                v-if="researchLoadError"
                class="skx-history__notice"
                role="status"
                :message="researchLoadError"
                :busy="retrying"
                @retry="retryLoad"
              />
              <button
                v-else-if="!researchRows.length"
                type="button"
                class="skx-history__start"
                @click="startDeepResearch"
              >
                연구 시작하기
                <svg class="skx-history__start-chev" viewBox="0 0 5 8" aria-hidden="true" focusable="false">
                  <path
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                    d="M0.102681 0.132319C0.250461 -0.031888 0.503377 -0.0452041 0.667584 0.102576L4.66758 3.70243C4.75187 3.77828 4.8 3.88635 4.8 3.99974C4.80001 4.11314 4.75188 4.2212 4.6676 4.29706L0.667599 7.89731C0.5034 8.04509 0.250484 8.03179 0.102695 7.86759C-0.0450943 7.70339 -0.0317915 7.45048 0.132408 7.30269L3.80207 3.99977L0.132424 0.697222C-0.0317831 0.549442 -0.0450996 0.296526 0.102681 0.132319Z"
                  />
                </svg>
              </button>
              <template v-if="!researchFolded">
              <div
                v-if="confirming === 'research'"
                class="skx-history__confirm"
                role="alertdialog"
                :aria-label="`${DEEP_RESEARCH} 기록 전체 삭제 확인`"
                aria-describedby="skx-history-research-confirm"
                @keydown.esc.stop="closeConfirm('research')"
              >
                <p id="skx-history-research-confirm" class="skx-history__confirm-text">{{ CLEAR_TEXT.research }}</p>
                <div class="skx-history__confirm-actions">
                  <button
                    ref="researchConfirmBtn"
                    type="button"
                    class="skx-history__confirm-btn is-danger"
                    @click="clearGroup('research')"
                  >
                    지우기
                  </button>
                  <button type="button" class="skx-history__confirm-btn" @click="closeConfirm('research')">
                    취소
                  </button>
                </div>
              </div>

              <ul v-if="researchRows.length" class="skx-history__list">
                <li
                  v-for="h in researchRows"
                  :key="h.id"
                  :data-history-id="h.id"
                  :class="['skx-history__row', rowConfirm === h.id && 'is-confirming']"
                >
                  <div class="skx-history__row-main">
                    <button
                      type="button"
                      :class="['skx-history-item', h.id === activeId && 'is-active']"
                      :aria-current="h.id === activeId ? 'page' : undefined"
                      @click="go(h)"
                    >
                      <span class="skx-history-item__query">{{ h.title }}</span>
                      <span class="skx-history-item__meta">
                        <!-- 진행 중인 연구 줄은 배지 대신 지금 단계('근거 수집 중' 등, 숫자 없이)와 아래 진행 막대(후배 시안, 2026-10-14).
                             승인 대기·완료·실패·취소 줄은 차분한 배지 하나 -->
                        <span v-if="stageOf(h)" class="skx-history-item__stage">{{ stageOf(h) }}</span>
                        <span v-else :class="['skx-history-badge', `is-${badgeOf(h).tone}`]">{{ badgeOf(h).label }}</span>
                        <span class="skx-history-item__time">{{ formatHistoryTime(entryTime(h)) }}</span>
                      </span>
                      <!-- 단계 글이 이미 읽히므로 막대는 눈으로만 보는 보조다. 지난 단계까지 채우고 지금 단계 구간은 옅게 깜빡인다 -->
                      <span v-if="progressOf(h)" class="skx-history-item__progress" aria-hidden="true">
                        <span class="skx-history-item__progress-fill" :style="{ width: pct(progressOf(h)?.start) }"></span>
                        <span
                          v-if="(progressOf(h)?.span ?? 0) > 0"
                          class="skx-history-item__progress-now"
                          :style="{ left: pct(progressOf(h)?.start), width: pct(progressOf(h)?.span) }"
                        ></span>
                      </span>
                    </button>
                    <button
                      type="button"
                      class="skx-history-item__del"
                      :aria-label="`'${h.title}' 기록 삭제`"
                      :aria-expanded="rowConfirm === h.id"
                      @click="toggleRowConfirm(h.id)"
                    >
                      <img src="/img/ico-delete.svg" alt="" />
                    </button>
                  </div>
                  <div
                    v-if="rowConfirm === h.id"
                    class="skx-history__confirm skx-history__confirm--row"
                    role="alertdialog"
                    :aria-label="`'${h.title}' 기록 삭제 확인`"
                    :aria-describedby="`skx-row-confirm-${h.id}`"
                    @keydown.esc.stop="cancelRowConfirm(h.id)"
                  >
                    <p :id="`skx-row-confirm-${h.id}`" class="skx-history__confirm-text">{{ ROW_CLEAR_TEXT.research }}</p>
                    <div class="skx-history__confirm-actions">
                      <button
                        type="button"
                        class="skx-history__confirm-btn is-danger"
                        data-row-confirm
                        @click="removeRow(h.id, $event)"
                      >
                        지우기
                      </button>
                      <button type="button" class="skx-history__confirm-btn" @click="cancelRowConfirm(h.id)">취소</button>
                    </div>
                  </div>
                </li>
              </ul>
              <!-- 3줄을 넘는 연구는 구분선 아래 '이전 연구 [n]' 한 줄로 이 자리에서 펼친다(시안 C — 숫자는 최근 검색의 종류 칩과
                   같은 칩, 오른쪽 끝 ⌄, 펼치면 '접기') -->
              <button
                v-if="researchHiddenCount > 0 || researchExpanded"
                type="button"
                :class="['skx-history__older', researchExpanded && 'is-expanded']"
                :aria-expanded="researchExpanded"
                :aria-label="older.ariaLabel"
                @click="researchExpanded = !researchExpanded"
              >
                <span>{{ older.label }}</span>
                <span v-if="older.count !== null" class="skx-history-chip" aria-hidden="true">{{ older.count }}</span>
                <svg class="skx-history__older-chev" viewBox="0 0 8 5" aria-hidden="true" focusable="false">
                  <path
                    fill-rule="evenodd"
                    clip-rule="evenodd"
                    d="M7.86768 0.102681C8.03189 0.250461 8.0452 0.503377 7.89742 0.667584L4.29757 4.66758C4.22172 4.75187 4.11365 4.8 4.00026 4.8C3.88686 4.80001 3.7788 4.75188 3.70294 4.6676L0.102695 0.667599C-0.0450944 0.5034 -0.0317915 0.250484 0.132408 0.102695C0.296607 -0.0450943 0.549523 -0.0317915 0.697312 0.132408L4.00023 3.80207L7.30278 0.132424C7.45056 -0.0317831 7.70347 -0.0450996 7.86768 0.102681Z"
                  />
                </svg>
              </button>
              </template>
            </section>

            <!-- 진짜 빈 목록일 때만 — 못 읽은 묶음은 제자리에서 실패를 말한다. 사이드바 모양(작은 회색 한 줄)을 지키려 공통 빈 상태
                 블록(SkxErrorState empty)을 쓰지 않는다 — 공통 디자인 훅 밖이다(오류 화면 모음에도 그렇게 적었다) -->
            <p
              v-if="!deepReadRows.length && !researchRows.length && !recentRows.length && !researchLoadError && !recentLoadError"
              class="skx-history__empty"
              role="status"
            >
              {{ SIDEBAR_EMPTY }}
            </p>

            <!-- 최근 검색: 소장자료·논문. 목록을 못 읽었으면 줄이 없어도 묶음을 그려 그 자리에 실패를 말한다(통째로 숨으면 기록이 없는 것처럼 보인다) -->
            <section
              v-if="recentRows.length || recentLoadError"
              class="skx-history__group"
              aria-labelledby="skx-history-recent"
            >
              <div class="skx-history__head">
                <h2 id="skx-history-recent" class="skx-history__title" tabindex="-1">최근 검색</h2>
                <button
                  v-if="recentRows.length"
                  ref="recentClearBtn"
                  type="button"
                  class="skx-history__clear"
                  @click="openConfirm('recent')"
                >
                  전체 삭제
                </button>
              </div>
              <SkxInlineError
                v-if="recentLoadError"
                class="skx-history__notice"
                role="status"
                :message="recentLoadError"
                :busy="retrying"
                @retry="retryLoad"
              />

              <div
                v-if="confirming === 'recent'"
                class="skx-history__confirm"
                role="alertdialog"
                aria-label="최근 검색 기록 전체 삭제 확인"
                aria-describedby="skx-history-recent-confirm"
                @keydown.esc.stop="closeConfirm('recent')"
              >
                <p id="skx-history-recent-confirm" class="skx-history__confirm-text">{{ CLEAR_TEXT.recent }}</p>
                <div class="skx-history__confirm-actions">
                  <button
                    ref="recentConfirmBtn"
                    type="button"
                    class="skx-history__confirm-btn is-danger"
                    @click="clearGroup('recent')"
                  >
                    지우기
                  </button>
                  <button type="button" class="skx-history__confirm-btn" @click="closeConfirm('recent')">
                    취소
                  </button>
                </div>
              </div>

              <ul v-if="recentRows.length" class="skx-history__list">
                <li
                  v-for="r in recentRows"
                  :key="r.entry.id"
                  :data-history-id="r.entry.id"
                  :class="['skx-history__row', rowConfirm === r.entry.id && 'is-confirming']"
                >
                  <div class="skx-history__row-main">
                    <button
                      type="button"
                      :class="['skx-history-item', r.entry.id === activeId && 'is-active']"
                      :aria-current="r.entry.id === activeId ? 'page' : undefined"
                      @click="go(r.entry)"
                    >
                      <span class="skx-history-item__query">{{ r.entry.title }}</span>
                      <span class="skx-history-item__meta">
                        <span class="skx-history-chip">{{ r.label }}</span>
                        <span class="skx-history-item__time">{{ formatHistoryTime(entryTime(r.entry)) }}</span>
                      </span>
                    </button>
                    <button
                      type="button"
                      class="skx-history-item__del"
                      :aria-label="`'${r.entry.title}' 기록 삭제`"
                      :aria-expanded="rowConfirm === r.entry.id"
                      @click="toggleRowConfirm(r.entry.id)"
                    >
                      <img src="/img/ico-delete.svg" alt="" />
                    </button>
                  </div>
                  <div
                    v-if="rowConfirm === r.entry.id"
                    class="skx-history__confirm skx-history__confirm--row"
                    role="alertdialog"
                    :aria-label="`'${r.entry.title}' 기록 삭제 확인`"
                    :aria-describedby="`skx-row-confirm-${r.entry.id}`"
                    @keydown.esc.stop="cancelRowConfirm(r.entry.id)"
                  >
                    <p :id="`skx-row-confirm-${r.entry.id}`" class="skx-history__confirm-text">{{ ROW_CLEAR_TEXT.recent }}</p>
                    <div class="skx-history__confirm-actions">
                      <button
                        type="button"
                        class="skx-history__confirm-btn is-danger"
                        data-row-confirm
                        @click="removeRow(r.entry.id, $event)"
                      >
                        지우기
                      </button>
                      <button type="button" class="skx-history__confirm-btn" @click="cancelRowConfirm(r.entry.id)">취소</button>
                    </div>
                  </div>
                </li>
              </ul>
            </section>

            <!-- 브라우저 ID 를 저장하지 못하는 브라우저(사이트 데이터 차단) — 새로 고칠 때마다 새 ID 라 이전 기록이 사이드바에서 사라진다.
                 목록 아래에 한 번만 알린다. 그 브라우저에서는 어느 화면에나 계속 남는 안내라 status(낭독기가 화면마다 끊고 읽지 않게) -->
            <SkxInlineError
              v-if="storageBlocked"
              class="skx-history__notice"
              role="status"
              :message="SIDEBAR_NOTICE.storageBlocked"
            />
          </template>
        </ClientOnly>
      </div>
    </div>

    <!-- 프로필(목업, 숨김) — 설정(톱니)은 목업이 아니라 진짜라 늘 보인다. 접힌 띠에서는 숨는다(.skx-settings 는 접히면 통째로 숨고, 프로필 줄은 아바타만 남는다) -->
    <div v-if="SHOW_MOCKS" class="skx-profile">
      <img class="skx-profile__avatar" src="/img/ico-avatar.svg" alt="" />
      <span class="skx-profile__name">김랜드</span>
      <SettingsMenu />
    </div>
    <div v-else class="skx-settings">
      <SettingsMenu />
    </div>
  </aside>
  <!-- 서랍이 열렸을 때 본문을 덮는 어두운 막 — 누르면 닫힌다(좁은 화면에서만 그려진다) -->
  <div :class="['skx-lnb-scrim', drawerOpen && 'is-open']" aria-hidden="true" @click="closeDrawer(true)"></div>
</template>

<script setup lang="ts">
import type { HistoryEntry } from "~/types/history";
import { useBrowserIdPersisted } from "~/composables/useBrowserId";
import { useHistory } from "~/composables/useHistory";
import { safeLocalStorage } from "~/utils/browserId";
import { SHOW_MOCKS } from "~/utils/featureFlags";
import { readV1Map } from "~/utils/historyStore";
import { activeIdFor, routeFor } from "~/utils/historyRoute";
import { deepResearchStartRoute } from "~/utils/landingStart";
import { DEEP_READ, DEEP_RESEARCH } from "~/utils/brand";
import {
  type DeepReadHistoryItem,
  deepReadRoute,
  firstQuestion,
  questionCount,
  useDeepReadHistory,
} from "~/utils/deepReadHistory";
import { NARROW_QUERY, trapTabTarget } from "~/utils/sidebarDrawer";
import {
  SIDEBAR_EMPTY,
  SIDEBAR_NOTICE,
  countLiveResearch,
  entryTime,
  formatHistoryTime,
  groupLoadError,
  groupSidebarHistory,
  hasActiveResearch,
  isLiveResearch,
  type SidebarGroupKey,
} from "~/utils/sidebarGroups";
import { olderToggle, stageProgress, statusStageLine, type StageRange } from "~/utils/sidebarResearch";

// collapsed — 페이지가 정하는 접힘(채팅·작업대가 열린 동안). foldOnEnter — 이 화면에 들어올 때 띠로 접힌 채 연다(상세 화면)
const props = defineProps<{ collapsed?: boolean; foldOnEnter?: boolean }>();
const emit = defineEmits<{ cart: []; save: [] }>();

// DeepResearch 묶음이 처음 보이는 행 수 — 넘치는 만큼은 구분선 아래 '이전 연구 [n]' 한 줄로 이 자리에서 펼친다(5 → 3, 사용자 2026-10-26)
const RESEARCH_ROW_LIMIT = 3;
type ClearGroup = SidebarGroupKey;
// 묶음별 전체 삭제 확인 문구 — 최근 검색은 도서·논문만, 딥리서치는 따로 지운다. 해요체, 문장마다 줄을 바꾼다(.skx-history__confirm-text pre-line)
const CLEAR_TEXT: Record<ClearGroup, string> = {
  research: `${DEEP_RESEARCH} 기록을 모두 지울까요?\n보고서 자체는 지워지지 않아요.`,
  recent: `최근 검색 기록(소장자료·논문)을 모두 지울까요?\n${DEEP_RESEARCH} 기록은 지워지지 않아요.`,
};
// 한 줄 삭제 확인 문구 — 묶음 전체 삭제와 같은 말투
const ROW_CLEAR_TEXT: Record<ClearGroup, string> = {
  research: "이 연구 기록을 지울까요?\n보고서 자체는 지워지지 않아요.",
  recent: "이 검색 기록을 지울까요?",
};
// 진행 중인 연구가 있을 때만 도는 다시 읽기 간격 — 30초는 본문과 세 번 어긋났다(2026-10-14 운영 확인). 연구 화면이 열려 있으면
// 그 화면이 상태를 바로 싣고(useHistory.setResearchStatus), 다른 화면에서는 이 간격으로 따라잡는다
const POLL_MS = 10_000;

const route = useRoute();
const router = useRouter();
const history = useHistory();

// open 에는 사용자가 누른 상태만 둔다 — 채팅 때문에 접힌 상태를 여기 쓰면, 채팅을 연 채 페이지를 떠날 때
// 되돌릴 기회가 없어 다음 페이지들까지 접힌 채로 남는다. 넓은 화면(>768px)의 펼침·접힘(띠)만 이 값이 정한다
const open = useState<boolean>("skx:lnb-open", () => true);
// 상세 화면(foldOnEnter)의 접힘 — 상세에서는 검색 기록을 거의 쓰지 않아 그 폭을 DeepRead 창에 준다(요청 2026-10-23).
// 상세 화면은 이 값만 읽고 쓴다 — open 은 읽지도 쓰지도 않아, 상세에서 펼치고 접어도 다른 화면은 사용자가 고른 그대로다.
// 띠의 [사이드바 열기]·현미경이 풀고, [사이드바 접기]가 다시 접는다
const folded = ref(!!props.foldOnEnter);
const isCollapsed = computed(() => !!props.collapsed || (props.foldOnEnter ? folded.value : !open.value));

/** 넓은 화면에서 펼친다 — 상세 화면은 그 화면의 접힘만 푼다 */
function unfold() {
  if (props.foldOnEnter) folded.value = false;
  else open.value = true;
}

// ── 좁은 화면(≤768px)의 서랍 ─────────────────────────────
// 좁은 화면에서는 위 open 값과 상관없이 늘 닫힌 채 시작한다(데스크톱에서 펼쳐 둔 상태가 휴대폰에 그대로 열려 나오지 않게) —
// 서랍의 열림은 이 컴포넌트가 따로 갖는다(페이지마다 새로 마운트되므로 페이지를 옮기면 저절로 닫힌다). 서랍은 본문을 밀지 않고 위를 덮는다
const narrow = ref(false);
const drawerOpen = ref(false);
const asideEl = ref<HTMLElement | null>(null);
const openerBtn = ref<HTMLButtonElement | null>(null);
const collapseBtn = ref<HTMLButtonElement | null>(null);
let narrowMql: MediaQueryList | null = null;

const SCROLL_LOCK_CLASS = "skx-scroll-lock";

async function openDrawer() {
  drawerOpen.value = true;
  await nextTick();
  collapseBtn.value?.focus({ preventScroll: true });
}

/** 서랍 닫기 — restoreFocus 면 [사이드바 열기]로 초점을 되돌린다(Esc·막·접기 버튼) */
function closeDrawer(restoreFocus: boolean) {
  if (!drawerOpen.value) return;
  drawerOpen.value = false;
  if (restoreFocus) void nextTick(() => openerBtn.value?.focus({ preventScroll: true }));
}

/** 서랍 안의 [사이드바 접기] — 좁은 화면에서는 서랍을 닫고, 넓은 화면에서는 띠로 접는다(상세 화면은 그 화면 안에서만 접는다) */
function collapse() {
  if (narrow.value) closeDrawer(true);
  else if (props.foldOnEnter) folded.value = true;
  else open.value = false;
}

function onDrawerEsc(e: KeyboardEvent) {
  if (e.key === "Escape" && drawerOpen.value) {
    e.preventDefault();
    closeDrawer(true);
  }
}

/** 서랍이 열린 동안 Tab 이 서랍 밖(본문)으로 새지 않게 돌린다 */
function onAsideKeydown(e: KeyboardEvent) {
  if (e.key !== "Tab" || !narrow.value || !drawerOpen.value || !asideEl.value) return;
  const items = [
    ...asideEl.value.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ].filter((el) => el.getClientRects().length > 0);
  const target = trapTabTarget(items, document.activeElement as HTMLElement | null, e.shiftKey);
  if (target) {
    e.preventDefault();
    target.focus();
  }
}

function onNarrowChange(e: MediaQueryListEvent) {
  narrow.value = e.matches;
  // 넓은 화면으로 돌아가거나 좁아지는 순간에는 서랍을 닫아 둔다(열린 채 폭이 바뀌어 막이 남지 않게)
  drawerOpen.value = false;
}

// 서랍이 열린 동안 본문 스크롤을 잠근다(Esc 도 이때만 듣는다)
watch(drawerOpen, (isOpen) => {
  document.documentElement.classList.toggle(SCROLL_LOCK_CLASS, isOpen);
  if (isOpen) document.addEventListener("keydown", onDrawerEsc);
  else document.removeEventListener("keydown", onDrawerEsc);
});
// 같은 페이지 안에서 주소가 바뀌어도(최근 검색 눌러 결과 전환 등) 서랍은 닫는다
watch(
  () => route.fullPath,
  () => closeDrawer(false),
);
const v1Map = ref<Record<string, string>>({});
// 첫 목록을 읽기 전·읽지 못한 때에 '기록 없음'을 띄우지 않으려고 쓴다(최상위 ref 라 템플릿에서 풀린다)
const { loaded, failedKinds } = history;
// 브라우저 ID 를 저장하지 못하는 브라우저 — 마운트 뒤에 정한다(서버 렌더에는 알 수 없어 수화가 어긋나지 않게)
const storageBlocked = ref(false);
// 목록 실패 안내의 [다시 시도] 진행 중 — 연타해도 한 번만 다시 읽는다
const retrying = ref(false);

const researchExpanded = ref(false);
const confirming = ref<ClearGroup | null>(null);
// 갈 곳이 없어진 초점은 [새 검색]으로, 그 버튼이 없으면(숨겼던 10-14~15 처럼) 로고(첫 화면 링크)로 보낸다
const newSearchBtn = ref<HTMLButtonElement | null>(null);
const homeLink = ref<HTMLAnchorElement | null>(null);
const researchClearBtn = ref<HTMLButtonElement | null>(null);
const recentClearBtn = ref<HTMLButtonElement | null>(null);
const researchConfirmBtn = ref<HTMLButtonElement | null>(null);
const recentConfirmBtn = ref<HTMLButtonElement | null>(null);

const groups = computed(() =>
  groupSidebarHistory(history.entries.value, {
    researchLimit: researchExpanded.value ? undefined : RESEARCH_ROW_LIMIT,
  }),
);
const researchRows = computed(() => groups.value.research);
const researchHiddenCount = computed(() => groups.value.researchTotal - groups.value.research.length);
const older = computed(() => olderToggle(researchExpanded.value, researchHiddenCount.value));
const recentRows = computed(() => groups.value.recent);
// 진행 중 수·폴링은 자르기 전 전체에서 센다 — 접힌 줄 밖의 진행 중 건도 놓치지 않는다
const liveCount = computed(() => countLiveResearch(history.entries.value));
const hasLiveResearch = computed(() => liveCount.value > 0);
// 접힌 띠의 현미경 점 — 진행 중이거나 승인을 기다리는 연구가 있다는 신호(펼친 묶음의 '진행 중 N' 자리)
const researchActive = computed(() => hasActiveResearch(history.entries.value));
const activeId = computed(() => activeIdFor(route.path, route.query, v1Map.value));
// 묶음별 목록 실패 안내(없으면 null) — 줄 수는 자르기 전 전체로 센다
const researchLoadError = computed(() => groupLoadError("research", failedKinds.value, groups.value.researchTotal));
const recentLoadError = computed(() => groupLoadError("recent", failedKinds.value, recentRows.value.length));

// 실패 안내의 [다시 시도] — 세 종류를 모두 다시 읽는다(서버에 닿지 못한 실패는 보통 두 묶음이 함께다). refresh 는 실패해도 던지지 않는다
async function retryLoad() {
  if (retrying.value) return;
  retrying.value = true;
  try {
    await history.refresh();
  } finally {
    retrying.value = false;
  }
}

// 기록이 하나씩 지워져 묶음이 비면 열려 있던 확인창을 닫고, 3줄 이하로 줄면 펼침도 푼다 —
// 안 풀면 다음에 기록이 늘 때 처음부터 펼쳐진 채 나타난다
watch(
  () => [groups.value.researchTotal, recentRows.value.length] as const,
  ([researchTotal, recentCount]) => {
    if ((confirming.value === "research" && !researchTotal) || (confirming.value === "recent" && !recentCount)) {
      confirming.value = null;
    }
    if (researchTotal <= RESEARCH_ROW_LIMIT) researchExpanded.value = false;
  },
);

const OPENER = { research: researchClearBtn, recent: recentClearBtn } as const;
const CONFIRM = { research: researchConfirmBtn, recent: recentConfirmBtn } as const;

// 확인창이 열리면 확인 버튼으로, 닫히면 연 버튼으로 초점을 옮긴다 — 키보드 사용자가 자리를 잃지 않게
async function openConfirm(group: ClearGroup) {
  rowConfirm.value = null;
  confirming.value = group;
  await nextTick();
  CONFIRM[group].value?.focus();
}

async function closeConfirm(group: ClearGroup) {
  confirming.value = null;
  await nextTick();
  OPENER[group].value?.focus();
}

// 지운 묶음은 화면에서 사라져 되돌아갈 버튼이 없다 — 맨 위 새 검색 버튼으로 초점을 옮긴다
async function clearGroup(group: ClearGroup) {
  confirming.value = null;
  // 목록은 바로 비고(상태가 먼저 지운다) 서버 응답은 기다리지 않는다. 최근 검색은 도서·논문 둘이라 하이브리드 저장소가 줄 세워 보낸다
  const done =
    group === "research"
      ? history.clear("research")
      : Promise.all([history.clear("book"), history.clear("paper")]);
  await nextTick();
  const opener = OPENER[group].value;
  (opener?.isConnected ? opener : (newSearchBtn.value ?? homeLink.value))?.focus();
  await done;
}

// ── 한 줄 삭제 확인 ──────────────────────────────────────
// 휴지통은 바로 지우지 않고 그 줄 아래에 확인을 펼친다(한 번에 한 줄). 다시 누르면 접는다. 묶음 전체 삭제 확인과는 함께 열리지 않는다
const rowConfirm = ref<string | null>(null);

async function toggleRowConfirm(id: string) {
  confirming.value = null;
  rowConfirm.value = rowConfirm.value === id ? null : id;
  if (!rowConfirm.value) return;
  // 열리면 [지우기]에 초점 — 묶음 확인(openConfirm)과 같다. 엔터 한 번 더면 지워지고, Esc·[취소]면 휴지통으로 돌아간다
  await nextTick();
  asideEl.value?.querySelector<HTMLButtonElement>("[data-row-confirm]")?.focus({ preventScroll: true });
}

// [취소]·Esc — 확인이 걷히면 초점을 그 줄의 휴지통으로 돌린다
async function cancelRowConfirm(id: string) {
  rowConfirm.value = null;
  await nextTick();
  const rows = asideEl.value?.querySelectorAll<HTMLButtonElement>(".skx-history-item__del") ?? [];
  [...rows].find((btn) => btn.closest("li")?.dataset.historyId === id)?.focus();
}

// 확인을 연 줄이 다른 곳(다른 탭·폴링)에서 지워지면 확인도 거둔다
watch(
  () => history.entries.value,
  (entries) => {
    if (rowConfirm.value && !entries.some((e) => e.id === rowConfirm.value)) rowConfirm.value = null;
  },
);

// 행을 지우면 초점을 다음 행으로, 마지막 행이었으면 그 묶음 제목으로, 묶음이 사라지면 새 검색 버튼으로 옮긴다
function removeRow(id: string, ev: Event) {
  rowConfirm.value = null;
  const li = (ev.currentTarget as HTMLElement).closest("li");
  const nextRow = li?.nextElementSibling?.querySelector<HTMLElement>(".skx-history-item") ?? null;
  const title = li?.closest("section")?.querySelector<HTMLElement>(".skx-history__title") ?? null;
  void history.remove(id);
  void nextTick(() => {
    const target = nextRow?.isConnected ? nextRow : title?.isConnected ? title : (newSearchBtn.value ?? homeLink.value);
    target?.focus();
  });
}

// ── 접힌 띠(데스크톱) ─────────────────────────────────────
// 이름표 문구가 곧 버튼의 aria-label 이다 — 이름표는 눈으로만 보는 보조라 스크린리더에는 숨긴다
const RAIL_TIPS = { open: "사이드바 열기", new: "새 검색", research: DEEP_RESEARCH } as const;
type RailKey = keyof typeof RAIL_TIPS;
const railTip = ref<RailKey | null>(null);

// 마우스는 올리면, 키보드는 초점이 갈 때만 보인다 — 터치나 마우스 클릭으로 간 초점은 이름표를 남기지 않는다
function showTip(key: RailKey, e: Event) {
  if (e instanceof PointerEvent && e.pointerType === "touch") return;
  if (e.type === "focus" && !(e.target as HTMLElement).matches(":focus-visible")) return;
  railTip.value = key;
}

function hideTip(key: RailKey) {
  if (railTip.value === key) railTip.value = null;
}

// 이름표가 떠 있는 동안 어디서든 Esc 로 닫는다(마우스만 올린 때도) — 다시 올려야 또 뜬다
function onTipEsc(e: KeyboardEvent) {
  if (e.key === "Escape") railTip.value = null;
}
watch(railTip, (now, before) => {
  if (now && !before) document.addEventListener("keydown", onTipEsc);
  if (!now && before) document.removeEventListener("keydown", onTipEsc);
});

function expandFromRail() {
  railTip.value = null;
  unfold();
}

// 현미경 — 사이드바를 펼치고 DeepResearch 묶음 머리로 초점을 옮긴다(펼침 폭 전환이 끝나기 전에도 머리는 이미 그려져 있다)
async function openResearchFromRail() {
  railTip.value = null;
  unfold();
  await nextTick();
  const head = document.getElementById("skx-history-research");
  head?.focus({ preventScroll: true });
  head?.scrollIntoView({ block: "nearest" });
}

// 랜딩의 첫 화면으로 간다. '/' 에서 결과(?q=·?h=)를 보던 중이면 쿼리가 사라지는 이동이라,
// pages/index.vue 의 route.query watch 가 같은 페이지에서 goLanding 으로 결과를 걷는다 — 이쪽에서 따로 비울 상태는 없다
function newSearch() {
  confirming.value = null;
  rowConfirm.value = null;
  void router.push({ path: "/" });
}

// 연구 기록이 없을 때 DeepResearch 패널의 [연구 시작하기] — 랜딩에서 논문 패널 + 딥리서치 모드를 켠다(pages/index.vue 가 ?start= 를 받는다).
// '/' 에 이미 있어도 쿼리가 바뀌는 이동이라 같은 길로 받는다
function startDeepResearch() {
  confirming.value = null;
  rowConfirm.value = null;
  void router.push(deepResearchStartRoute());
}

function go(h: HistoryEntry) {
  router.push(routeFor(h));
}

// 딥리드 기록 — 최신 DEEP_READ_ROW_LIMIT 개, 넘치면 '이전 대화 [n]'으로 펼친다. 누르면 그 자료 상세에서 딥리드 창을 연 채로(?chat=1)
const DEEP_READ_ROW_LIMIT = 3;
const deepRead = useDeepReadHistory();
const deepReadExpanded = ref(false);
const deepReadTotal = computed(() => deepRead.items.value.length);
const deepReadRows = computed(() =>
  deepReadExpanded.value ? deepRead.items.value : deepRead.items.value.slice(0, DEEP_READ_ROW_LIMIT),
);
const deepReadHiddenCount = computed(() => deepReadTotal.value - deepReadRows.value.length);
const olderDeepRead = computed(() => olderToggle(deepReadExpanded.value, deepReadHiddenCount.value, "대화"));
watch(deepReadTotal, (n) => {
  if (n <= DEEP_READ_ROW_LIMIT) deepReadExpanded.value = false;
});

// DeepRead·DeepResearch 묶음 접힘 — 머리를 누르면 머리 한 줄만 남는다(사용자 2026-10-26: 기록이 없을 때의 [연구 시작하기]처럼
// 작게). 보는 사람마다의 편의라 이 브라우저에 기억한다 — 저장소가 막히면 이 화면에서만. 빈 DeepResearch 묶음은 접지 않는다
// ([연구 시작하기]가 늘 보이게)
type FoldGroup = "deepread" | "research";
const FOLD_KEY = "skx-sidebar-fold-v1";
const fold = reactive<Record<FoldGroup, boolean>>({ deepread: false, research: false });
const researchFolded = computed(() => fold.research && researchRows.value.length > 0);
function toggleFold(group: FoldGroup) {
  fold[group] = !fold[group];
  if (group === "research" && confirming.value === "research") confirming.value = null;
  rowConfirm.value = null;
  try {
    safeLocalStorage()?.setItem(FOLD_KEY, JSON.stringify(fold));
  } catch {
    // 막힌 저장소 — 이 화면에서만 접힌다
  }
}
onMounted(() => {
  try {
    const saved = JSON.parse(safeLocalStorage()?.getItem(FOLD_KEY) || "{}") as Partial<Record<FoldGroup, unknown>>;
    fold.deepread = saved.deepread === true;
    fold.research = saved.research === true;
  } catch {
    // 읽지 못하면 펼친 채로
  }
});
function isDeepReadActive(d: DeepReadHistoryItem): boolean {
  return route.path === deepReadRoute(d).path && route.query.dr === d.id;
}
// 같은 자료 화면이면 지금 쿼리(검색어·관련도)를 지킨 채 대화만 바꾼다 — 상세 머리의 관련도 배지가 사라지지 않게(리뷰 지적)
function goDeepRead(d: DeepReadHistoryItem) {
  const to = deepReadRoute(d);
  void router.push(route.path === to.path ? { path: to.path, query: { ...route.query, ...to.query } } : to);
}

function badgeOf(h: HistoryEntry): { label: string; tone: string } {
  const status = h.kind === "research" ? h.research?.status : undefined;
  switch (status) {
    case "completed":
      return { label: "완료", tone: "done" };
    case "failed":
      return { label: "실패", tone: "failed" };
    case "canceled":
      return { label: "취소", tone: "canceled" };
    case "awaiting_approval":
      return { label: "승인 대기 중", tone: "waiting" };
    case undefined:
      return { label: "알 수 없음", tone: "unknown" };
    default:
      return { label: "진행 중", tone: "running" };
  }
}

// 진행 중인 연구 줄(배지 '진행 중'과 같은 상태 — sidebarGroups.LIVE_STATUSES)에만 기록 목록이 주는 잡의 상태·stage 로 짧은 단계 글을
// 단다(utils/sidebarResearch — 숫자 없이). 그것을 내려고 잡을 따로 읽지 않는다(사용자 결정 2026-10-13). 승인 대기·완료·실패·취소 줄은
// 배지가 말한다
function stageOf(h: HistoryEntry): string | null {
  return h.kind === "research" && isLiveResearch(h) ? statusStageLine(h.research) : null;
}

// 진행 중인 연구 줄 아래 막대 — 지난 단계까지 채움 + 지금 단계 구간(연구 화면 큰 막대와 같은 경계, utils/sidebarResearch.stageProgress).
// 단계 글과 같은 줄에만
function progressOf(h: HistoryEntry): StageRange | null {
  return h.kind === "research" && isLiveResearch(h) ? stageProgress(h.research) : null;
}

function pct(n: number | undefined): string {
  return `${(n ?? 0) * 100}%`;
}

let pollTimer: ReturnType<typeof setInterval> | null = null;

// 접혀 있어도 읽는다 — 접힌 띠의 현미경 점이 낡지 않게(숨은 탭에서만 건너뛴다)
function pollOnce() {
  if (document.hidden) return;
  void history.refresh("research");
}

function syncPolling() {
  if (hasLiveResearch.value && !pollTimer) pollTimer = setInterval(pollOnce, POLL_MS);
  if (!hasLiveResearch.value && pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function onVisibility() {
  if (!document.hidden && hasLiveResearch.value) pollOnce();
}

watch(hasLiveResearch, syncPolling);
// 펼치는 순간 바로 한 번 새로 읽는다 — 진행 중 배지가 낡았을 수 있다
watch(isCollapsed, (collapsed, wasCollapsed) => {
  if (wasCollapsed && !collapsed && hasLiveResearch.value) pollOnce();
});
watch(drawerOpen, (isOpen) => {
  if (isOpen && hasLiveResearch.value) pollOnce();
});

onMounted(() => {
  narrowMql = window.matchMedia(NARROW_QUERY);
  narrow.value = narrowMql.matches;
  narrowMql.addEventListener("change", onNarrowChange);
  v1Map.value = readV1Map(safeLocalStorage());
  storageBlocked.value = !useBrowserIdPersisted();
  void history.load();
  // 업그레이드 뒤 첫 로드에서는 이전이 서버 응답을 받아야 대응표가 생긴다 — 옛 ?restore= 주소의 강조를 그때 맞춘다
  void history.migrated().then(() => {
    v1Map.value = readV1Map(safeLocalStorage());
  });
  syncPolling();
  document.addEventListener("visibilitychange", onVisibility);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onTipEsc);
  document.removeEventListener("keydown", onDrawerEsc);
  document.documentElement.classList.remove(SCROLL_LOCK_CLASS);
  narrowMql?.removeEventListener("change", onNarrowChange);
  if (pollTimer) clearInterval(pollTimer);
  document.removeEventListener("visibilitychange", onVisibility);
});
</script>

<style scoped>
/* 검색기록 영역 전체가 스크롤한다 — 묶음마다 따로 스크롤하지 않는다 */
.skx-history__body {
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.skx-history__group {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.skx-history__group .skx-history__list {
  overflow: visible;
}
/* DeepResearch·DeepRead 묶음 카드(시안): 흰 5% 유리 — 사이드바가 이미 흐려져 있어 이 카드는 흐림 없이 바탕만 얹는다 */
.skx-history__group--research,
.skx-history__group--deepread {
  padding: 0.6rem;
  background: var(--skx-frost-side-card);
  border-radius: var(--skx-radius-md);
  box-shadow: var(--skx-frost-hilite);
  /* 카드 안의 글 톤은 사이드바 글 톤을 올리기 전 그대로(제목 청록·행 글·시간·칩) */
  --skx-ink: var(--skx-research-ink);
  --skx-ink-2: var(--skx-research-ink-2);
  --skx-gray-1: var(--skx-research-gray-1);
  --skx-gray-2: var(--skx-research-gray-2);
  --skx-teal-ink: var(--skx-research-teal-ink);
  --skx-ico-filter: var(--skx-research-ico-filter);
}
.skx-history__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.2rem 0.3rem;
  min-height: 1.2rem;
}
.skx-history__head-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.2rem 0.3rem;
  min-width: 0;
}
.skx-history__group .skx-history__title {
  color: var(--skx-teal-ink);
}
/* 묶음 머리 접기 — 머리 줄 전체가 단추(제목 · 접히면 수 칩). 화살표 없이 머리만 누른다(사용자 2026-10-26) */
.skx-history__head-main,
.skx-history__head > .skx-history__title {
  flex: 1;
  min-width: 0;
}
.skx-history__head-main > .skx-history__title {
  flex: 1;
  min-width: 0;
}
.skx-history__fold {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  font: inherit;
  letter-spacing: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
}
.skx-history__fold:hover {
  color: var(--skx-primary);
}
.skx-history__fold:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
  border-radius: var(--skx-radius-sm);
}
/* 접힌 DeepResearch 머리의 점 — 진행 중이거나 승인을 기다리는 연구가 있다(접힌 띠의 현미경 점과 같은 뜻) */
.skx-history__fold-dot {
  flex: none;
  width: 0.3rem;
  height: 0.3rem;
  border-radius: 50%;
  background: var(--skx-primary);
}
.skx-history__clear {
  flex: none;
  padding: 0.1rem 0.4rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  font-size: 0.6rem;
  color: var(--skx-gray-1);
  cursor: pointer;
}
.skx-history__clear:hover {
  color: var(--skx-primary);
  background: var(--skx-frost-bg);
}
/* 이전 연구 [n] / 접기 — 묶음 맨 아래 구분선 아래의 한 줄(시안 C). 숫자는 최근 검색의 종류 칩(.skx-history-chip)과 같은 칩,
   오른쪽 끝 아래 화살표(피그마 sidebar 의 8×5 아이콘)는 펼치면 뒤집힌다 */
.skx-history__older {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
  margin-top: 0.2rem;
  padding: 0.5rem 0.4rem 0.2rem;
  border: none;
  border-top: 1px solid var(--skx-line);
  border-radius: 0;
  background: none;
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--skx-teal-ink);
  text-align: left;
  cursor: pointer;
}
.skx-history__older:hover {
  color: var(--skx-primary);
}
.skx-history__older:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
.skx-history__older-chev {
  flex: none;
  margin-left: auto;
  width: 0.4rem;
  height: 0.25rem;
  fill: var(--skx-teal-ink);
  transition:
    transform 0.15s,
    fill 0.15s;
}
.skx-history__older:hover .skx-history__older-chev {
  fill: var(--skx-primary);
}
.skx-history__older.is-expanded .skx-history__older-chev {
  transform: rotate(180deg);
}
@media (prefers-reduced-motion: reduce) {
  .skx-history__older-chev {
    transition: none;
  }
}
/* 진행 중인 연구 줄의 단계 글 — 배지 자리의 글자(테두리·바탕 없음), 좁으면 말줄임 */
/* 진행 중인 줄의 '~ 중' 라벨(탐색 중·보고서 작성 중 등)과 '승인 대기 중' 배지는 산호 알약(연구 화면 단계 칩의 꼬리표와 같은 색) — 끝난 줄의
   유리 알약(완료·취소)과 한눈에 갈린다(사용자 결정 2026-10-16 — 전에는 바탕 없는 글이라 묻혔다). 라이트에서는 검정 알약 */
.skx-history-item__stage {
  min-width: 0;
  overflow: hidden;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
  color: var(--skx-on-accent);
  background: var(--skx-primary);
  white-space: nowrap;
  text-overflow: ellipsis;
}
/* 진행 막대 — 옅은 홈(선 색 — 라이트의 흰 유리 면은 분홍 사이드바에서 보이지 않는다) 위에 포인트 색(다크 산호·라이트 검정 — 위
   '~ 중' 라벨과 같은 색). 지난 단계까지는 채우고, 지금 단계 구간은 옅게 깜빡인다 — 단계 안의 진행은 모르므로 한 값으로 칠하지
   않는다(연구 화면 막대의 값이 늘 이 구간 안이라 둘이 어긋나 보이지 않는다). 단계가 바뀌면 부드럽게 늘어난다 */
.skx-history-item__progress {
  position: relative;
  display: block;
  width: 100%;
  height: 3px;
  overflow: hidden;
  border-radius: var(--skx-radius-pill);
  background: var(--skx-line);
}
.skx-history-item__progress-fill,
.skx-history-item__progress-now {
  position: absolute;
  top: 0;
  height: 100%;
  background: var(--skx-primary);
  transition:
    left 0.4s ease,
    width 0.4s ease;
}
.skx-history-item__progress-fill {
  left: 0;
}
.skx-history-item__progress-now {
  opacity: 0.35;
  animation: skx-stage-pulse 1.6s ease-in-out infinite alternate;
}
@keyframes skx-stage-pulse {
  from {
    opacity: 0.2;
  }
  to {
    opacity: 0.55;
  }
}
@media (prefers-reduced-motion: reduce) {
  .skx-history-item__progress-fill,
  .skx-history-item__progress-now {
    transition: none;
    animation: none;
  }
}
.skx-history__empty {
  margin: 0;
  padding: 0.8rem 0.4rem;
  font-size: 0.6rem;
  line-height: 1.6;
  color: var(--skx-gray-1);
}
/* 사이드바 안의 줄 안내(SkxInlineError — 목록 실패·저장 차단) — 모양은 공통 구역('[S] 공통 오류·빈 상태')이 정하고,
   여기서는 묶음 제목·줄 글과 같은 왼쪽 선(0.4rem)에 맞추기만 한다 */
.skx-history__notice {
  padding: 0.2rem 0.4rem;
}
/* 연구 기록이 없을 때 DeepResearch 패널 머리 아래의 [연구 시작하기 >] — 피그마 sidebar 알약 모양(흰 10% 면·오른쪽 화살표)을
   한 단계 크게(글 13px·안쪽 여백 넓게) — 빈 패널의 유일한 할 일이라(사용자 요청 2026-10-16) */
.skx-history__start {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.6rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: var(--skx-frost-bg);
  font-size: 0.65rem;
  font-weight: 600;
  line-height: 1.4;
  color: var(--skx-gray-1);
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s;
}
.skx-history__start-chev {
  width: 0.3rem;
  height: 0.48rem;
  fill: var(--skx-gray-1);
  transition: fill 0.15s;
}
.skx-history__start:hover {
  color: var(--skx-primary);
}
.skx-history__start:hover .skx-history__start-chev {
  fill: var(--skx-primary);
}
.skx-history__start:focus-visible {
  outline: 2px solid var(--skx-accent);
  outline-offset: 2px;
}
/* 휴지통은 줄 본체(제목·메타)의 세로 가운데에 선다 — 확인이 그 아래로 펼쳐져도 자리가 밀리지 않게 기준을 본체에 둔다 */
.skx-history__row-main {
  position: relative;
}
.skx-history__row .skx-history-item {
  padding-right: 1.6rem;
}
.skx-history-item__meta {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  width: 100%;
}
.skx-history-item__meta .skx-history-item__time {
  width: auto;
  color: var(--skx-gray-1);
}
.skx-history-item__del {
  position: absolute;
  top: 50%;
  right: 0.2rem;
  width: 1.2rem;
  height: 1.2rem;
  padding: 0.2rem;
  border: none;
  border-radius: var(--skx-radius-sm);
  background: none;
  opacity: 0;
  transform: translateY(-50%);
  cursor: pointer;
  transition: opacity 0.15s;
}
.skx-history__row:hover .skx-history-item__del,
.skx-history-item__del:focus-visible,
.skx-history__row.is-confirming .skx-history-item__del {
  opacity: 1;
}
/* 확인을 연 줄은 휴지통이 눌린 채 남는다 — 어느 줄을 지우려는지 보인다 */
.skx-history__row.is-confirming .skx-history-item__del {
  background: var(--skx-frost-bg);
}
/* 한 줄 삭제 확인 — 그 줄 바로 아래(휴지통 자리와 겹치지 않게 흐름 안)에 선다 */
.skx-history__confirm--row {
  margin: 0.2rem 0 0.4rem;
}
/* 아이콘 버튼 올림은 모두 같은 모양(살짝 둥근 네모 + 흰 10% 면) */
.skx-history-item__del:hover {
  background: var(--skx-frost-bg);
}
@media (hover: none) {
  .skx-history-item__del {
    opacity: 1;
  }
}
.skx-history-item__del img {
  width: 100%;
  height: 100%;
}
/* 종류 라벨(소장자료·논문) — 조용한 청록 알약 */
.skx-history-chip {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  background: var(--skx-glass-teal);
  color: var(--skx-teal-ink);
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
}
/* 상태 배지 — 후배 시안처럼 모두 옅은 유리 알약(2026-10-14 — 완료의 진한 초록·진행 중 산호 면·실패의 빨강을 걷었다). 바탕은 같고
   글자 톤으로만 가른다: 승인 대기(사용자가 움직일 차례)는 가장 밝게, 완료는 본문 보조색, 실패·취소·모름은 흐리게 */
.skx-history-badge {
  flex: none;
  padding: 0 0.3rem;
  border-radius: var(--skx-radius-pill);
  font-size: 0.6rem;
  font-weight: 600;
  line-height: 1.5;
  background: var(--skx-frost-bg);
  color: var(--skx-ink-2);
}
.skx-history-badge.is-waiting {
  color: var(--skx-on-accent);
  background: var(--skx-primary);
}
.skx-history-badge.is-failed,
.skx-history-badge.is-canceled,
.skx-history-badge.is-unknown {
  color: var(--skx-gray-1);
}
.skx-history__confirm {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.6rem;
  border: 1px solid var(--skx-glass-border);
  border-radius: var(--skx-radius-md);
  background: var(--skx-white);
}
.skx-history__confirm-text {
  margin: 0;
  font-size: 0.6rem;
  line-height: 1.5;
  color: var(--skx-ink);
  white-space: pre-line;
}
.skx-history__confirm-actions {
  display: flex;
  gap: 0.3rem;
  justify-content: flex-end;
}
.skx-history__confirm-btn {
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--skx-line);
  border-radius: var(--skx-radius-sm);
  background: var(--skx-white);
  font-size: 0.6rem;
  color: var(--skx-ink);
  cursor: pointer;
}
.skx-history__confirm-btn:hover {
  background: var(--skx-glass-teal);
}
.skx-history__confirm-btn.is-danger {
  border-color: var(--skx-danger);
  background: var(--skx-danger);
  color: var(--skx-on-accent);
}
</style>
