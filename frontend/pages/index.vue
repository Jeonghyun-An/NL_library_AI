<template>
  <div
    :class="['skovix', sidebarOpen ? 'sk-sidebar-open' : 'sk-sidebar-closed']"
  >
    <!-- ══ 사이드바 ═══════════════════════════════════════════ -->
    <aside class="sk-sidebar">
      <div class="sk-sidebar-top">
        <button class="sk-logo" @click="goLanding">
          <img src="/skovix-character.png" alt="SKOVIX" class="sk-logo-img" />
          <Transition name="sk-fade"
            ><span v-if="sidebarOpen" class="sk-logo-text"
              >SKOVIX</span
            ></Transition
          >
        </button>
        <button
          class="sk-sidebar-toggle"
          @click="sidebarOpen = !sidebarOpen"
          :title="sidebarOpen ? '사이드바 닫기' : '사이드바 열기'"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <polyline
              :points="sidebarOpen ? '15 18 9 12 15 6' : '9 18 15 12 9 6'"
            />
          </svg>
        </button>
      </div>

      <div v-if="sidebarOpen" class="sk-sidebar-body">
        <button class="sk-new-chat" @click="goLanding">
          <span class="sk-new-chat-icon">+</span>
          <span>새 채팅</span>
        </button>

        <nav class="sk-nav">
          <button class="sk-nav-item" @click="showCartToast">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <circle cx="9" cy="21" r="1" />
              <circle cx="20" cy="21" r="1" />
              <path
                d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"
              />
            </svg>
            대출 장바구니
          </button>
          <button class="sk-nav-item" @click="showSaveToast">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" />
            </svg>
            저장목록
          </button>
        </nav>

        <div class="sk-history-section">
          <p class="sk-history-label">검색기록</p>
          <div class="sk-history-list scrollbar-zinc">
            <button v-if="!history.length" class="sk-history-empty">
              검색 기록이 없습니다
            </button>
            <button
              v-for="h in history"
              :key="h.id"
              class="sk-history-item"
              :class="{ active: h.id === currentHistoryId }"
              @click="restoreHistory(h)"
            >
              <span class="sk-history-query">{{ h.query }}</span>
              <span class="sk-history-time">{{ formatTime(h.timestamp) }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-if="sidebarOpen" class="sk-sidebar-footer">
        <div class="sk-user-row">
          <div class="sk-avatar">김</div>
          <span class="sk-user-name">김랜드</span>
        </div>
        <button class="sk-settings-btn">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
        </button>
      </div>
    </aside>

    <!-- ══ 메인 콘텐츠 ═══════════════════════════════════════ -->
    <main class="sk-main">
      <!-- ── Landing ─────────────────────────────────────── -->
      <div v-if="view === 'landing'" class="sk-landing">
        <div class="sk-landing-hero">
          <p class="sk-hero-title">원하는 자료를 찾고 활용하는</p>
          <p class="sk-hero-title sk-hero-title--sub">
            가장 쉽고 편안한 검색을 경험해보세요!
          </p>
        </div>

        <!-- 도서/논문 모드 탭 -->
        <div class="sk-mode-tabs">
          <button
            :class="['sk-mode-tab', mode === 'book' && 'active']"
            @click="mode = 'book'"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
            도서검색
          </button>
          <button
            :class="['sk-mode-tab', mode === 'paper' && 'active']"
            @click="mode = 'paper'"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
              />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            논문검색
          </button>
        </div>

        <!-- 검색창 -->
        <div class="sk-landing-search">
          <SearchInput
            v-model="currentQuery"
            :disabled="loading"
            :placeholder="
              mode === 'book'
                ? '찾고싶은 도서를 문장으로 검색해보세요!'
                : '논문 주제나 키워드로 검색해보세요!'
            "
            @submit="handleSearch"
          />
        </div>

        <!-- 추천 검색어 칩 -->
        <div class="sk-suggestion-chips">
          <button
            v-for="chip in suggestions[mode]"
            :key="chip"
            class="sk-suggestion-chip"
            @click="handleChip(chip)"
          >
            {{ chip }}
          </button>
        </div>

        <!-- 시나리오 추천 배너 -->
        <div class="sk-scenario-banner" @click="navigateTo('/scenarios')">
          <div class="sk-scenario-icon-wrap">
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              stroke-width="2"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.35-4.35" />
            </svg>
          </div>
          <span class="sk-scenario-text">내 상황에 맞는 도서 추천받기</span>
          <span class="sk-scenario-arrow">›</span>
        </div>

        <!-- 신작도서 섹션 (더미) -->
        <div class="sk-newbooks">
          <p class="sk-newbooks-label">
            지금도 새로운 책이 업데이트 되고 있어요!
          </p>
          <div class="sk-newbooks-bar">
            <span class="sk-newbooks-tag">신작도서</span>
            <span class="sk-newbooks-count">1,245<sup>권</sup></span>
            <div class="sk-newbooks-covers">
              <div v-for="i in 5" :key="i" class="sk-cover-placeholder" />
            </div>
          </div>
        </div>
      </div>

      <!-- ── Results ──────────────────────────────────────── -->
      <div v-else-if="view === 'results'" class="sk-results">
        <!-- 상단 검색창 -->
        <div class="sk-results-topbar">
          <SearchInput
            v-model="currentQuery"
            :disabled="loading"
            @submit="handleSearch"
          />
        </div>

        <!-- AI 검색 결과 헤더 -->
        <div v-if="!loading" class="sk-results-header">
          <span class="sk-results-badge">AI 검색 결과</span>
          <span v-if="keywordChips.length" class="sk-results-keywords">
            키워드:
            <span v-for="kw in keywordChips" :key="kw" class="sk-kw-chip">{{
              kw
            }}</span>
          </span>
        </div>

        <!-- 로딩 -->
        <div v-if="loading" class="sk-loading-state">
          <div class="sk-spinner" />
          <p>AI가 {{ mode === "book" ? "도서" : "논문" }}를 검색 중입니다...</p>
        </div>

        <!-- 에러 -->
        <div v-if="searchError" class="sk-error">{{ searchError }}</div>

        <!-- BOOK: AI 큐레이션 박스 -->
        <div
          v-if="!loading && mode === 'book' && books.length"
          class="sk-curation-box"
        >
          <div class="sk-curation-header" @click="curationOpen = !curationOpen">
            <div class="sk-curation-avatar">y</div>
            <span class="sk-curation-title"
              >AI가 원하시는 도서를 찾았어요!</span
            >
            <div class="sk-curation-right">
              <span v-if="curationLoading" class="sk-curation-loading"
                >분석 중...</span
              >
              <span class="sk-curation-toggle">{{
                curationOpen ? "접기 ∧" : "펼치기 ∨"
              }}</span>
            </div>
          </div>
          <Transition name="sk-expand">
            <div
              v-if="curationOpen && (curation || curationLoading)"
              class="sk-curation-body"
            >
              <div
                v-if="curationLoading && !curation"
                class="sk-curation-skeleton"
              >
                분석 중...
              </div>
              <template v-if="curation">
                <p class="sk-curation-intro">{{ curation.intro }}</p>
                <ul class="sk-curation-list">
                  <li v-for="item in curation.items" :key="item.book_id">
                    • {{ item.reason }}
                  </li>
                </ul>
              </template>
            </div>
          </Transition>
        </div>

        <!-- PAPER: AI 핵심 요약 -->
        <div
          v-if="
            !loading &&
            mode === 'paper' &&
            (paperSummaryText || paperSummaryLoading)
          "
          class="sk-paper-summary"
        >
          <div class="sk-paper-summary-header">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
              />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
            </svg>
            AI 핵심 요약
            <span v-if="paperSummaryLoading" class="sk-streaming-dot">●</span>
          </div>
          <div class="sk-paper-summary-main">
            <div class="sk-paper-summary-body" v-html="renderedPaperSummary" />
            <!-- 답변이 인용한 문서 리스트 (우측) -->
            <ol
              v-if="paperSummarySources.length"
              class="sk-paper-summary-sources"
            >
              <li
                v-for="(src, i) in paperSummarySources"
                :key="src.book_id"
                class="sk-summary-source-item"
                @click="openDetail(src)"
              >
                <span class="sk-summary-source-num">{{ i + 1 }}</span>
                <div class="sk-summary-source-info">
                  <span class="sk-summary-source-title">{{
                    src.book_info?.title || src.book_id
                  }}</span>
                  <span class="sk-summary-source-authors">{{
                    src.book_info?.personal_author ||
                    src.book_info?.corporate_author ||
                    ""
                  }}</span>
                </div>
              </li>
            </ol>
          </div>
        </div>

        <!-- 결과 카드 목록 -->
        <div class="sk-card-list">
          <div
            v-for="item in books"
            :key="item.book_id"
            class="sk-result-card"
            style="cursor: pointer"
            @click="openDetail(item)"
          >
            <div class="sk-result-card-inner">
              <div class="sk-result-card-cover">
                <BookCover :book-id="item.book_id" />
              </div>
              <div class="sk-result-card-info">
                <div class="sk-result-card-meta">
                  <span
                    v-if="item.book_info?.grade"
                    class="sk-grade-badge"
                    >{{ item.book_info.grade }}</span
                  >
                  <span class="sk-match-badge"
                    >정합성
                    {{ Math.round((item.best_score || 0) * 100) }}%</span
                  >
                  <template
                    v-for="tag in parseThemes(item.book_info?.themes)"
                    :key="tag"
                  >
                    <span class="sk-hashtag">#{{ tag }}</span>
                  </template>
                </div>
                <h3 class="sk-result-title">
                  {{ item.book_info?.title || item.book_id }}
                  <span v-if="isAvailable(item)" class="sk-avail-badge"
                    >· 대출 가능</span
                  >
                </h3>
                <p class="sk-result-sub">
                  <span v-if="item.book_info?.material_type">{{
                    item.book_info.material_type
                  }}</span>
                  <span
                    v-if="
                      item.book_info?.personal_author ||
                      item.book_info?.corporate_author
                    "
                  >
                    ·
                    {{
                      item.book_info?.personal_author ||
                      item.book_info?.corporate_author
                    }}
                  </span>
                  <span v-if="item.book_info?.pub_date"
                    >· {{ item.book_info.pub_date?.slice(0, 4) }}</span
                  >
                  <span v-if="item.book_info?.publisher"
                    >· {{ item.book_info.publisher }}</span
                  >
                  <!-- KCI 전용 -->
                  <span v-if="item.book_info?.vol_issue">
                    · {{ item.book_info.vol_issue }}</span
                  >
                  <span v-if="item.book_info?.kci_citations != null">
                    · 인용수 {{ item.book_info.kci_citations }}</span
                  >
                </p>
                <div class="sk-result-actions">
                  <button
                    class="sk-btn-outline"
                    @click.stop="requestLoan(item)"
                  >
                    대출신청
                  </button>
                  <button class="sk-btn-outline" @click.stop="viewPdf(item)">
                    원문 보기
                  </button>
                  <button
                    v-if="mode === 'paper'"
                    class="sk-btn-outline"
                    @click.stop="openCitation(item)"
                  >
                    출처 인용
                  </button>
                  <button class="sk-btn-primary" @click.stop="openDetail(item)">
                    + 이 {{ mode === "paper" ? "논문과" : "책과" }} 대화하기
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── Detail ────────────────────────────────────────── -->
      <div v-else-if="view === 'detail' && selectedItem" class="sk-detail">
        <button class="sk-back-btn" @click="view = 'results'">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          검색 목록 돌아가기
        </button>

        <!-- 도서/논문 헤더 -->
        <div class="sk-detail-header">
          <div class="sk-detail-cover-wrap">
            <BookCover :book-id="selectedItem.book_id" size="large" />
          </div>
          <div class="sk-detail-meta">
            <div class="sk-result-card-meta">
              <span
                v-if="selectedItem.book_info?.grade"
                class="sk-grade-badge"
                >{{ selectedItem.book_info.grade }}</span
              >
              <span class="sk-match-badge"
                >정합성
                {{ Math.round((selectedItem.best_score || 0) * 100) }}%</span
              >
              <template
                v-for="tag in parseThemes(selectedItem.book_info?.themes)"
                :key="tag"
              >
                <span class="sk-hashtag">#{{ tag }}</span>
              </template>
            </div>
            <h2 class="sk-detail-title">{{ selectedItem.book_info?.title }}</h2>
            <p class="sk-detail-sub">
              <span v-if="selectedItem.book_info?.material_type">{{
                selectedItem.book_info.material_type
              }}</span>
              <span
                v-if="
                  selectedItem.book_info?.personal_author ||
                  selectedItem.book_info?.corporate_author
                "
              >
                ·
                {{
                  selectedItem.book_info?.personal_author ||
                  selectedItem.book_info?.corporate_author
                }}
              </span>
              <span v-if="selectedItem.book_info?.pub_date"
                >· {{ selectedItem.book_info.pub_date?.slice(0, 4) }}</span
              >
              <span v-if="selectedItem.book_info?.publisher"
                >· {{ selectedItem.book_info.publisher }}</span
              >
              <span v-if="selectedItem.book_info?.vol_issue"
                >· {{ selectedItem.book_info.vol_issue }}</span
              >
              <span v-if="selectedItem.book_info?.kci_citations != null"
                >· 인용수 {{ selectedItem.book_info.kci_citations }}</span
              >
            </p>
            <div class="sk-detail-actions">
              <button class="sk-btn-outline" @click="requestLoan(selectedItem)">
                대출신청
              </button>
              <button class="sk-btn-outline" @click="viewPdf(selectedItem)">
                원문 보기
              </button>
              <button class="sk-btn-primary" @click="showChat = !showChat">
                + 이 {{ mode === "paper" ? "논문과" : "책과" }} 대화하기
              </button>
              <button
                v-if="mode === 'paper'"
                class="sk-btn-outline"
                @click="openCitation(selectedItem)"
              >
                출처 인용
              </button>
            </div>
          </div>
        </div>

        <!-- 인라인 채팅 -->
        <BookChat
          v-show="showChat"
          :cnts-id="selectedItem.book_id"
          @close="showChat = false"
        />

        <!-- AI 큐레이션 탭 -->
        <section class="sk-section">
          <h3 class="sk-section-title">AI 큐레이션</h3>
          <div class="sk-tabs-row">
            <button
              v-for="tab in detailTabs"
              :key="tab.key"
              :class="['sk-tab-btn', detailTab === tab.key && 'active']"
              @click="switchDetailTab(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>
          <div class="sk-tab-panel">
            <!-- 추천하는 이유 (SSE) -->
            <div v-if="detailTab === 'reason'">
              <div v-if="reasonLoading" class="sk-streaming-text">
                추천 이유 생성 중...
              </div>
              <div
                v-else-if="reasonText"
                class="sk-prose"
                v-html="renderedReason"
              />
              <p v-else class="sk-empty-text">추천 이유 정보가 없습니다.</p>
            </div>
            <!-- 줄거리 -->
            <div v-if="detailTab === 'plot'">
              <p class="sk-prose-plain">
                {{ selectedItem.book_info?.plot || "줄거리 정보가 없습니다." }}
              </p>
            </div>
            <!-- 책 소개 -->
            <div v-if="detailTab === 'intro'">
              <p class="sk-prose-plain">
                {{
                  selectedItem.book_info?.introduction ||
                  "소개 정보가 없습니다."
                }}
              </p>
            </div>
            <!-- 읽고 난 후 -->
            <div v-if="detailTab === 'effect'">
              <p class="sk-prose-plain">
                {{ selectedItem.book_info?.read_effect || "정보가 없습니다." }}
              </p>
            </div>
            <!-- 초록 (논문) -->
            <div v-if="detailTab === 'abstract'">
              <p class="sk-prose-plain">
                {{
                  selectedItem.book_info?.abstract || "초록 정보가 없습니다."
                }}
              </p>
            </div>
          </div>
        </section>

        <!-- 상세 정보 -->
        <section class="sk-section">
          <h3 class="sk-section-title">상세 정보</h3>
          <table class="sk-info-table">
            <tbody>
              <tr>
                <th>표제/저자사항</th>
                <td>
                  {{
                    selectedItem.book_info?.title_responsibility ||
                    selectedItem.book_info?.title ||
                    "-"
                  }}
                </td>
                <th>발행사항</th>
                <td>
                  {{
                    [
                      selectedItem.book_info?.pub_place,
                      selectedItem.book_info?.publisher,
                      selectedItem.book_info?.pub_date,
                    ]
                      .filter(Boolean)
                      .join(", ") || "-"
                  }}
                </td>
              </tr>
              <tr>
                <th>형태사항</th>
                <td>{{ selectedItem.book_info?.extent || "-" }}</td>
                <th>총서사항</th>
                <td>{{ selectedItem.book_info?.series_title || "-" }}</td>
              </tr>
              <tr>
                <th>표준번호</th>
                <td>
                  {{
                    selectedItem.book_info?.isbn ||
                    selectedItem.book_info?.uci ||
                    "-"
                  }}
                </td>
                <th>분류기호</th>
                <td>
                  {{
                    [selectedItem.book_info?.kdc, selectedItem.book_info?.ddc]
                      .filter(Boolean)
                      .join(" → ") || "-"
                  }}
                </td>
              </tr>
              <tr>
                <th>주제명</th>
                <td>
                  {{
                    selectedItem.book_info?.subject ||
                    selectedItem.book_info?.keyword ||
                    "-"
                  }}
                </td>
                <th>언어</th>
                <td>{{ selectedItem.book_info?.language || "Korean" }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- 참고문헌 (논문) -->
        <section v-if="mode === 'paper'" class="sk-section">
          <h3
            class="sk-section-title sk-refs-toggle"
            @click="refsOpen = !refsOpen"
          >
            참고문헌
            <span class="sk-refs-caret">{{ refsOpen ? "▲" : "▼" }}</span>
          </h3>
          <Transition name="sk-expand">
            <div v-show="refsOpen" class="sk-refs-wrap">
              <ol
                v-if="selectedItem.book_info?.references?.length"
                class="sk-refs-list"
              >
                <li
                  v-for="(ref, i) in selectedItem.book_info.references"
                  :key="i"
                  class="sk-ref-item"
                >
                  {{ ref }}
                </li>
              </ol>
              <p v-else class="sk-empty-text">참고문헌 정보가 없습니다.</p>
            </div>
          </Transition>
        </section>

        <!-- AI 연관 추천 -->
        <section class="sk-section">
          <h3 class="sk-section-title">
            {{ mode === "paper" ? "AI 연관 논문 추천" : "AI 연관 도서 추천" }}
          </h3>
          <div class="sk-related-layout">
            <!-- 목록 -->
            <div class="sk-related-list">
              <div v-if="relatedLoading" class="sk-loading-small">
                불러오는 중...
              </div>
              <div v-else-if="!relatedItems.length" class="sk-empty-text">
                연관 추천 항목이 없습니다.
              </div>
              <div
                v-for="rel in relatedItems"
                :key="rel.book_id"
                :class="[
                  'sk-related-item',
                  selectedRelated?.book_id === rel.book_id && 'selected',
                ]"
                @click="selectedRelated = rel"
              >
                <BookCover :book-id="rel.book_id" class="sk-related-thumb" />
                <div class="sk-related-item-info">
                  <span class="sk-related-item-title">{{
                    rel.book_info?.title || rel.book_id
                  }}</span>
                  <span class="sk-match-small"
                    >정합성 {{ Math.round((rel.score || 0) * 100) }}%</span
                  >
                </div>
              </div>
            </div>
            <!-- 우측 미리보기 -->
            <div class="sk-related-preview">
              <template v-if="selectedRelated">
                <BookCover
                  :book-id="selectedRelated.book_id"
                  class="sk-related-preview-cover"
                />
                <h4 class="sk-related-preview-title">
                  {{ selectedRelated.book_info?.title }}
                </h4>
                <p class="sk-related-preview-sub">
                  {{
                    selectedRelated.book_info?.personal_author ||
                    selectedRelated.book_info?.corporate_author
                  }}
                </p>
                <button
                  class="sk-btn-primary sk-related-detail-btn"
                  @click="openRelatedDetail(selectedRelated)"
                >
                  상세 보기
                </button>
              </template>
              <div v-else class="sk-related-hint">
                <div class="sk-related-hint-icon">📚</div>
                <p>추천도서를 클릭해주세요</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <!-- ══ 출처 인용 모달 (결과 카드·상세 공용) ══════════════════ -->
    <CitationModal
      :open="citationModal"
      :book-id="citationBook?.book_id ?? null"
      :references="citationBook?.book_info?.references ?? []"
      @close="citationModal = false"
    />

    <!-- ══ PDF 뷰어 ══════════════════════════════════════════ -->
    <PdfViewer
      v-if="pdfOpen && selectedItem"
      :cnts-id="selectedItem.book_id"
      :title="selectedItem.book_info?.title"
      @close="pdfOpen = false"
    />

    <!-- ══ 토스트 ════════════════════════════════════════════ -->
    <Teleport to="body">
      <Transition name="sk-toast">
        <div v-if="toast" class="sk-toast">{{ toast }}</div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { marked } from "marked";
import type { BookChunkGroup } from "~/types/search";

// ── 상수 ──────────────────────────────────────────────────
const SUGGESTIONS: Record<string, string[]> = {
  book: [
    "한국 경제에 대해 알고싶은데 책 추천해줄래?",
    "북한 경제 관련 리포트 써야하는데 도움되는 책",
    "수출 관련 보고서 참조 가능한 도서 찾아줄래?",
  ],
  paper: [
    "딥러닝 기반 자연어 처리 최신 연구",
    "한국어 감성 분석 논문 추천",
    "의료 AI 임상 적용 사례 연구",
  ],
};

const config = useRuntimeConfig();
const apiBase = config.public.apiBase as string;

// ── 세션 ──────────────────────────────────────────────────
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getSessionId(): string {
  if (!process.client) return "";
  let sid = localStorage.getItem("sid");
  if (!sid) {
    sid = generateUUID();
    localStorage.setItem("sid", sid);
  }
  return sid;
}

// ── 뷰 상태 ───────────────────────────────────────────────
const view = ref<"landing" | "results" | "detail">("landing");
const mode = ref<"book" | "paper">("book");
const sidebarOpen = ref(true);

// ── 검색 ──────────────────────────────────────────────────
const currentQuery = ref("");
const rewrittenQuery = ref("");
const loading = ref(false);
const searchError = ref("");
const books = ref<BookChunkGroup[]>([]);
const keywordChips = ref<string[]>([]);
const currentHistoryId = ref("");

// ── 큐레이션 (도서) ────────────────────────────────────────
const curation = ref<any>(null);
const curationOpen = ref(true);
const curationLoading = ref(false);

// ── 논문 핵심 요약 SSE ─────────────────────────────────────
const paperSummaryText = ref("");
const paperSummaryLoading = ref(false);
// AI 요약이 참조한 문서(상위 N개) — 본문 (1)(2)… 번호와 인덱스 대응
const paperSummarySources = ref<BookChunkGroup[]>([]);

const renderedPaperSummary = computed(() =>
  paperSummaryText.value
    ? (marked.parse(paperSummaryText.value) as string)
    : "",
);

// ── 상세 ──────────────────────────────────────────────────
const selectedItem = ref<BookChunkGroup | null>(null);
const detailTab = ref("reason");
const reasonText = ref("");
const reasonLoading = ref(false);
const showChat = ref(false);
const pdfOpen = ref(false);
const refsOpen = ref(true);

const detailTabs = computed(() =>
  mode.value === "paper"
    ? [
        { key: "abstract", label: "초록" },
        { key: "intro", label: "논문 소개" },
      ]
    : [
        { key: "reason", label: "추천하는 이유" },
        { key: "plot", label: "줄거리" },
        { key: "intro", label: "책 소개" },
        { key: "effect", label: "책을 읽고 난 후" },
      ],
);

const renderedReason = computed(() =>
  reasonText.value ? (marked.parse(reasonText.value) as string) : "",
);

// ── 연관 추천 ──────────────────────────────────────────────
const relatedItems = ref<any[]>([]);
const relatedLoading = ref(false);
const selectedRelated = ref<any>(null);

// ── 출처 인용 ──────────────────────────────────────────────
const citationModal = ref(false);
const citationBook = ref<BookChunkGroup | null>(null);

// ── 토스트 ────────────────────────────────────────────────
const toast = ref("");

// ── 검색 기록 ─────────────────────────────────────────────
const history = ref<any[]>([]);

onMounted(async () => {
  if (!process.client) return;
  try {
    const sid = getSessionId();
    const data = await $fetch<any[]>(`${apiBase}/books/history/${sid}`);
    if (Array.isArray(data)) history.value = data;
  } catch {
    /* 기록 없음 */
  }
});

// ── 유틸 ──────────────────────────────────────────────────
const suggestions = SUGGESTIONS;

function parseThemes(themes?: string | null): string[] {
  if (!themes) return [];
  return themes
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean)
    .slice(0, 3);
}

function isAvailable(_item: BookChunkGroup): boolean {
  return false; // 소장 정보 없음 — 더미
}

function formatTime(ts: string | number): string {
  if (!ts) return "";
  const d = new Date(ts);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "방금";
  if (diff < 3600) return `${Math.floor(diff / 60)}분 전`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}시간 전`;
  return d.toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" });
}

function showToast(msg: string) {
  toast.value = msg;
  setTimeout(() => {
    toast.value = "";
  }, 2500);
}

function showCartToast() {
  showToast("대출 장바구니 기능은 준비 중입니다.");
}
function showSaveToast() {
  showToast("저장목록 기능은 준비 중입니다.");
}

// ── 검색 ──────────────────────────────────────────────────
async function handleSearch(query: string) {
  if (!query.trim()) return;
  currentQuery.value = query;
  loading.value = true;
  searchError.value = "";
  books.value = [];
  curation.value = null;
  curationOpen.value = true;
  paperSummaryText.value = "";
  keywordChips.value = [];
  view.value = "results";

  try {
    const endpoint =
      mode.value === "paper"
        ? `${apiBase}/papers/search`
        : `${apiBase}/books/search`;
    const data = await $fetch<any>(endpoint, {
      method: "POST",
      headers: { "x-session-id": getSessionId() },
      body: {
        query,
        mode: "book",
        top_k: 5,
        use_rewrite: true,
        use_rerank: true,
      },
    });

    if (data?.books) {
      books.value = data.books;
      rewrittenQuery.value = data.rewritten_query || query;
      // 첫 번째 결과의 themes로 키워드 칩 채우기
      const firstThemes = parseThemes(data.books[0]?.book_info?.themes);
      if (firstThemes.length) keywordChips.value = firstThemes;
    }

    // 히스토리 로컬 추가
    history.value.unshift({
      id: Date.now().toString(),
      query,
      timestamp: new Date().toISOString(),
    });

    // 후속 AI 처리 (검색 완료 후 병렬 실행)
    if (mode.value === "book" && books.value.length) {
      fetchCuration();
    } else if (mode.value === "paper" && books.value.length) {
      fetchPaperSummary(query);
    }
  } catch (e: any) {
    searchError.value =
      e?.data?.detail || e?.message || "검색 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
}

function handleChip(chip: string) {
  currentQuery.value = chip;
  handleSearch(chip);
}

function goLanding() {
  view.value = "landing";
  currentQuery.value = "";
  books.value = [];
  curation.value = null;
  selectedItem.value = null;
}

function restoreHistory(h: any) {
  currentQuery.value = h.query;
  currentHistoryId.value = h.id;
  handleSearch(h.query);
}

// ── 큐레이션 (도서) ────────────────────────────────────────
async function fetchCuration() {
  const topBooks = books.value.slice(0, 3);
  if (!topBooks.length) return;
  curationLoading.value = true;
  try {
    const data = await $fetch<any>(`${apiBase}/books/curate`, {
      method: "POST",
      body: {
        query: currentQuery.value,
        book_ids: topBooks.map((b) => b.book_id),
        scores: topBooks.map((b) => b.best_score || 0),
        rewritten_query: rewrittenQuery.value,
      },
    });
    curation.value = data;
  } catch {
    /* 큐레이션 실패 시 조용히 무시 */
  } finally {
    curationLoading.value = false;
  }
}

// ── 논문 핵심 요약 SSE ─────────────────────────────────────
async function fetchPaperSummary(query: string) {
  paperSummaryLoading.value = true;
  paperSummaryText.value = "";
  // 요약에 투입하는 상위 N개를 인용 문서 리스트로 노출 (본문 번호와 인덱스 일치)
  paperSummarySources.value = books.value.slice(0, 5);
  const papers = books.value.slice(0, 5).map((b) => ({
    book_id: b.book_id,
    title: b.book_info?.title || "",
    authors:
      b.book_info?.personal_author || b.book_info?.corporate_author || "",
    best_chunk_text: b.chunks?.[0]?.text || "",
  }));
  try {
    const resp = await fetch(`${apiBase}/papers/summary/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, papers }),
    });
    await readSSE(resp, (json) => {
      if (json.text) paperSummaryText.value += json.text;
    });
  } catch {
    /* SSE 실패 — 조용히 */
  } finally {
    paperSummaryLoading.value = false;
  }
}

// ── 상세 열기 ──────────────────────────────────────────────
function openDetail(item: BookChunkGroup) {
  if (mode.value === "book") {
    // 도서 → 별도 상세 페이지로 이동
    navigateTo(
      `/books/${item.book_id}?q=${encodeURIComponent(currentQuery.value)}&score=${item.best_score || 0}`,
    );
    return;
  }
  // 논문 → 기존 인라인 detail 유지 (논문 전용 기능 포함)
  selectedItem.value = item;
  view.value = "detail";
  detailTab.value = "abstract";
  showChat.value = false;
  relatedItems.value = [];
  selectedRelated.value = null;
  fetchRelated(item.book_id);
}

function openRelatedDetail(rel: any) {
  const fakeGroup: BookChunkGroup = {
    book_id: rel.book_id,
    book_info: rel.book_info,
    best_score: rel.score || 0,
    chunks: [],
  };
  openDetail(fakeGroup);
}

function switchDetailTab(key: string) {
  detailTab.value = key;
  if (key === "reason" && !reasonText.value && selectedItem.value) {
    fetchReason(selectedItem.value);
  }
}

// ── 추천 이유 SSE ──────────────────────────────────────────
async function fetchReason(item: BookChunkGroup) {
  reasonLoading.value = true;
  reasonText.value = "";
  try {
    const resp = await fetch(`${apiBase}/books/reason/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: currentQuery.value,
        book_id: item.book_id,
        chunk_texts: item.chunks?.map((c) => c.text) ?? [],
        rewritten_query: rewrittenQuery.value,
      }),
    });
    await readSSE(resp, (json) => {
      if (json.text) reasonText.value += json.text;
      if (json.keywords?.length && !keywordChips.value.length)
        keywordChips.value = json.keywords;
    });
  } catch {
    /* 추천 이유 실패 */
  } finally {
    reasonLoading.value = false;
  }
}

// ── 연관 추천 ──────────────────────────────────────────────
async function fetchRelated(cntsId: string) {
  relatedLoading.value = true;
  relatedItems.value = [];
  try {
    const endpoint =
      mode.value === "paper" ? `${apiBase}/papers/${cntsId}/related` : null; // 도서 연관 추천은 미구현 — 빈 상태 표시
    if (!endpoint) return;
    const data = await $fetch<any>(endpoint);
    relatedItems.value = data?.results || [];
  } catch {
    /* 연관 추천 실패 */
  } finally {
    relatedLoading.value = false;
  }
}

// ── 출처 인용 ──────────────────────────────────────────────
// 출처 인용 모달 열기 — 결과 카드·상세 공용 (CitationModal 컴포넌트가 데이터 처리)
function openCitation(item: BookChunkGroup) {
  citationBook.value = item;
  citationModal.value = true;
}

// ── 대출 신청 / PDF ────────────────────────────────────────
function requestLoan(item: BookChunkGroup) {
  showToast(
    `"${item.book_info?.title || item.book_id}" 대출 신청 기능은 준비 중입니다.`,
  );
}

function viewPdf(item: BookChunkGroup) {
  selectedItem.value = item;
  pdfOpen.value = true;
}

// ── SSE 헬퍼 ──────────────────────────────────────────────
async function readSSE(resp: Response, onEvent: (json: any) => void) {
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop()!;
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]") return;
      try {
        onEvent(JSON.parse(raw));
      } catch {
        /* skip */
      }
    }
  }
}
</script>

<style scoped>
/* ── 전체 레이아웃 ────────────────────────────────────────── */
.skovix {
  display: flex;
  height: 100vh;
  background: var(--bg);
  overflow: hidden;
}

/* ── 사이드바 ─────────────────────────────────────────────── */
.sk-sidebar {
  display: flex;
  flex-direction: column;
  width: 240px;
  min-width: 240px;
  background: var(--surface);
  border-right: 1px solid var(--line);
  transition:
    width 0.25s,
    min-width 0.25s;
  overflow: hidden;
}
.sk-sidebar-closed .sk-sidebar {
  width: 56px;
  min-width: 56px;
}
.sk-sidebar-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 14px;
  border-bottom: 1px solid var(--line);
}
.sk-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}
.sk-logo-img {
  width: 28px;
  height: 28px;
  object-fit: contain;
}
.sk-logo-text {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
}
.sk-sidebar-toggle {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  padding: 4px;
  border-radius: 6px;
  display: flex;
  align-items: center;
}
.sk-sidebar-toggle:hover {
  background: var(--bg);
  color: var(--ink);
}
.sk-sidebar-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  padding: 12px;
  gap: 6px;
  overflow: hidden;
}
.sk-new-chat {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 14px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink);
  transition: background 0.15s;
}
.sk-new-chat:hover {
  background: var(--lilac);
}
.sk-new-chat-icon {
  font-size: 16px;
  font-weight: 300;
  color: var(--accent);
}
.sk-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}
.sk-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  background: none;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  color: #555;
  transition: background 0.15s;
  text-align: left;
}
.sk-nav-item:hover {
  background: var(--bg);
  color: var(--ink);
}
.sk-history-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-top: 8px;
}
.sk-history-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  padding: 0 4px 6px;
}
.sk-history-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.sk-history-empty {
  font-size: 12px;
  color: #bbb;
  padding: 8px 4px;
  background: none;
  border: none;
  text-align: left;
}
.sk-history-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.sk-history-item:hover,
.sk-history-item.active {
  background: var(--lilac);
}
.sk-history-query {
  font-size: 12px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 190px;
}
.sk-history-time {
  font-size: 10px;
  color: #aaa;
}
.sk-sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border-top: 1px solid var(--line);
}
.sk-user-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sk-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}
.sk-user-name {
  font-size: 13px;
  color: var(--ink);
}
.sk-settings-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  padding: 4px;
  border-radius: 6px;
  display: flex;
}
.sk-settings-btn:hover {
  color: var(--ink);
}

/* ── 메인 ─────────────────────────────────────────────────── */
.sk-main {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

/* ── Landing ──────────────────────────────────────────────── */
.sk-landing {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 40px 40px;
  max-width: 720px;
  margin: 0 auto;
  width: 100%;
}
.sk-landing-hero {
  text-align: center;
  margin-bottom: 28px;
}
.sk-hero-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.6;
}
.sk-hero-title--sub {
  font-size: 20px;
}
.sk-mode-tabs {
  display: flex;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 100px;
  padding: 4px;
  margin-bottom: 20px;
  gap: 4px;
}
.sk-mode-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  border-radius: 100px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  color: #777;
  font-weight: 500;
  transition: all 0.15s;
}
.sk-mode-tab.active {
  background: var(--ink);
  color: white;
}
.sk-landing-search {
  width: 100%;
  margin-bottom: 16px;
}
.sk-suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-bottom: 20px;
}
.sk-suggestion-chip {
  padding: 8px 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 20px;
  font-size: 12px;
  color: var(--ink);
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}
.sk-suggestion-chip:hover {
  background: var(--lilac);
  border-color: var(--accent);
}
.sk-scenario-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f0edff 0%, #e8e3ff 100%);
  border: 1px solid #d4ccff;
  border-radius: var(--radius);
  cursor: pointer;
  margin-bottom: 24px;
  transition: transform 0.1s;
}
.sk-scenario-banner:hover {
  transform: translateY(-1px);
}
.sk-scenario-icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.sk-scenario-text {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
}
.sk-scenario-arrow {
  font-size: 20px;
  color: var(--accent);
}
.sk-newbooks {
  width: 100%;
}
.sk-newbooks-label {
  font-size: 13px;
  color: #777;
  margin-bottom: 10px;
}
.sk-newbooks-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 16px 20px;
}
.sk-newbooks-tag {
  font-size: 12px;
  font-weight: 600;
  color: #777;
  white-space: nowrap;
}
.sk-newbooks-count {
  font-size: 22px;
  font-weight: 800;
  color: var(--ink);
  white-space: nowrap;
}
.sk-newbooks-count sup {
  font-size: 11px;
  font-weight: 500;
}
.sk-newbooks-covers {
  display: flex;
  gap: 6px;
  margin-left: auto;
}
.sk-cover-placeholder {
  width: 36px;
  height: 50px;
  background: var(--lilac);
  border-radius: 4px;
}

/* ── Results ──────────────────────────────────────────────── */
.sk-results {
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
  gap: 16px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
.sk-results-topbar {
}
.sk-results-header {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.sk-results-badge {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink);
}
.sk-results-keywords {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #777;
  flex-wrap: wrap;
}
.sk-kw-chip {
  padding: 3px 10px;
  background: var(--lilac);
  color: var(--accent);
  border-radius: 20px;
  font-size: 11px;
  font-weight: 600;
}
.sk-loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px;
  color: #888;
}
.sk-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--line);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.sk-error {
  padding: 12px 16px;
  background: #fff5f5;
  border: 1px solid #fcc;
  border-radius: var(--radius-sm);
  color: #c00;
  font-size: 13px;
}

/* 큐레이션 박스 */
.sk-curation-box {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.sk-curation-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  cursor: pointer;
}
.sk-curation-header:hover {
  background: var(--bg);
}
.sk-curation-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.sk-curation-title {
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
}
.sk-curation-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sk-curation-loading {
  font-size: 11px;
  color: var(--accent);
}
.sk-curation-toggle {
  font-size: 11px;
  color: #999;
  background: none;
  border: none;
  cursor: pointer;
}
.sk-curation-body {
  padding: 4px 16px 16px 54px;
  border-top: 1px solid var(--line);
}
.sk-curation-intro {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.7;
  margin-bottom: 8px;
}
.sk-curation-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sk-curation-list li {
  font-size: 12px;
  color: #555;
}

/* 논문 핵심 요약 */
.sk-paper-summary {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.sk-paper-summary-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  border-bottom: 1px solid var(--line);
}
.sk-streaming-dot {
  color: var(--accent);
  animation: blink 1s infinite;
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
.sk-paper-summary-body {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--ink);
  line-height: 1.8;
}
/* 본문(좌) + 인용 문서 리스트(우) 2단 — 퍼블리싱 시 정밀 스타일 교체 */
.sk-paper-summary-main {
  display: flex;
  align-items: flex-start;
}
.sk-paper-summary-main .sk-paper-summary-body {
  flex: 1;
  min-width: 0;
}
.sk-paper-summary-sources {
  flex: 0 0 280px;
  list-style: none;
  margin: 0;
  padding: 12px;
  border-left: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-self: stretch;
  max-height: 360px;
  overflow-y: auto;
}
.sk-summary-source-item {
  display: flex;
  gap: 8px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.sk-summary-source-item:hover {
  background: var(--lilac-2);
}
.sk-summary-source-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 6px;
  background: var(--lilac);
  color: var(--accent);
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.sk-summary-source-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.sk-summary-source-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.4;
}
.sk-summary-source-authors {
  font-size: 11px;
  color: var(--ink-3);
}
.sk-paper-summary-body :deep(h2) {
  font-size: 14px;
  font-weight: 700;
  margin: 12px 0 6px;
}
.sk-paper-summary-body :deep(p) {
  margin: 0 0 8px;
}

/* 결과 카드 */
.sk-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sk-result-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  cursor: pointer;
  transition: box-shadow 0.15s;
}
.sk-result-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}
.sk-result-card-inner {
  display: flex;
  gap: 16px;
  padding: 16px;
}
.sk-result-card-cover {
  width: 64px;
  min-width: 64px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
}
.sk-result-card-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sk-result-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.sk-match-badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent);
  background: var(--lilac);
  padding: 2px 8px;
  border-radius: 20px;
}
.sk-grade-badge {
  font-size: 11px;
  font-weight: 700;
  color: #2563eb;
  background: #e0ecff;
  padding: 2px 8px;
  border-radius: 20px;
}
.sk-hashtag {
  font-size: 11px;
  color: var(--accent);
  background: var(--lilac);
  padding: 2px 8px;
  border-radius: 20px;
}
.sk-avail-badge {
  font-size: 11px;
  color: #0a0;
  font-weight: 500;
}
.sk-result-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}
.sk-result-sub {
  font-size: 12px;
  color: #888;
  margin: 0;
}
.sk-result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* 버튼 공용 */
.sk-btn-outline {
  padding: 6px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.sk-btn-outline:hover {
  background: var(--bg);
}
.sk-btn-primary {
  padding: 6px 14px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.sk-btn-primary:hover {
  background: var(--accent-deep);
}

/* ── Detail ───────────────────────────────────────────────── */
.sk-detail {
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
  gap: 24px;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
}
.sk-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: #888;
  padding: 0;
  margin-bottom: -8px;
}
.sk-back-btn:hover {
  color: var(--ink);
}
.sk-detail-header {
  display: flex;
  gap: 20px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 20px;
}
.sk-detail-cover-wrap {
  width: 100px;
  min-width: 100px;
  height: 140px;
  border-radius: 8px;
  overflow: hidden;
}
.sk-detail-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sk-detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  margin: 0;
}
.sk-detail-sub {
  font-size: 13px;
  color: #888;
  margin: 0;
}
.sk-detail-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

/* 섹션 */
.sk-section {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  overflow: hidden;
}
.sk-section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  margin: 0;
}
/* 참고문헌 아코디언 — 퍼블리싱 시 정밀 스타일 교체 */
.sk-refs-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}
.sk-refs-caret {
  font-size: 11px;
  color: var(--ink-3, #6a6b76);
}
.sk-refs-list {
  margin: 0;
  padding: 16px 20px 16px 40px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sk-ref-item {
  font-size: 12.5px;
  color: var(--ink-2, #3a3b46);
  line-height: 1.6;
}
.sk-refs-wrap .sk-empty-text {
  padding: 16px 20px;
}
.sk-tabs-row {
  display: flex;
  padding: 12px 16px;
  gap: 4px;
  border-bottom: 1px solid var(--line);
}
.sk-tab-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 20px;
  background: none;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.sk-tab-btn.active {
  background: var(--accent);
  color: white;
  font-weight: 600;
}
.sk-tab-panel {
  padding: 16px 20px;
  min-height: 80px;
}
.sk-streaming-text {
  color: var(--accent);
  font-size: 13px;
}
.sk-prose {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.8;
}
.sk-prose :deep(h2) {
  font-size: 14px;
  font-weight: 700;
  margin: 12px 0 6px;
}
.sk-prose :deep(p) {
  margin: 0 0 8px;
}
.sk-prose-plain {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.8;
  margin: 0;
}
.sk-empty-text {
  font-size: 13px;
  color: #bbb;
}

/* 상세 정보 테이블 */
.sk-info-table {
  width: 100%;
  border-collapse: collapse;
}
.sk-info-table th,
.sk-info-table td {
  padding: 10px 16px;
  font-size: 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
}
.sk-info-table th {
  color: #888;
  font-weight: 500;
  white-space: nowrap;
  width: 110px;
}
.sk-info-table td {
  color: var(--ink);
}
.sk-info-table tr:last-child th,
.sk-info-table tr:last-child td {
  border-bottom: none;
}

/* 연관 추천 */
.sk-related-layout {
  display: flex;
  gap: 16px;
  padding: 16px;
}
.sk-related-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 280px;
  min-width: 280px;
}
.sk-loading-small {
  font-size: 12px;
  color: #bbb;
  padding: 8px;
}
.sk-related-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid var(--line);
  cursor: pointer;
  transition: background 0.1s;
}
.sk-related-item:hover,
.sk-related-item.selected {
  background: var(--lilac);
  border-color: var(--accent);
}
.sk-related-thumb {
  width: 36px;
  min-width: 36px;
  height: 50px;
  border-radius: 4px;
  overflow: hidden;
}
.sk-related-item-info {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
}
.sk-related-item-title {
  font-size: 12px;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
}
.sk-match-small {
  font-size: 11px;
  color: var(--accent);
}
.sk-related-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 8px;
}
.sk-related-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px;
  color: #ccc;
}
.sk-related-hint-icon {
  font-size: 32px;
}
.sk-related-hint p {
  font-size: 13px;
  color: #aaa;
}
.sk-related-preview-cover {
  width: 80px;
  height: 112px;
  border-radius: 8px;
  overflow: hidden;
}
.sk-related-preview-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  text-align: center;
}
.sk-related-preview-sub {
  font-size: 12px;
  color: #888;
  text-align: center;
}
.sk-related-detail-btn {
  margin-top: 4px;
}

/* ── 출처 인용 모달 ──────────────────────────────────────── */
.sk-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.sk-modal {
  background: var(--surface);
  border-radius: var(--radius);
  width: 520px;
  max-width: 90vw;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
}
.sk-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line);
  font-size: 15px;
  font-weight: 700;
}
.sk-modal-close {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #aaa;
}
.sk-modal-close:hover {
  color: var(--ink);
}
.sk-modal-body {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sk-citation-loading {
  font-size: 13px;
  color: #bbb;
  text-align: center;
  padding: 12px;
}
.sk-citation-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px;
  background: var(--bg);
  border-radius: var(--radius-sm);
}
.sk-citation-label {
  font-size: 11px;
  font-weight: 600;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.sk-citation-text {
  font-size: 13px;
  color: var(--ink);
  line-height: 1.7;
  margin: 0;
}
.sk-copy-btn {
  align-self: flex-end;
  padding: 5px 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.sk-copy-btn:hover {
  background: var(--lilac);
  border-color: var(--accent);
  color: var(--accent);
}

/* ── 토스트 ──────────────────────────────────────────────── */
.sk-toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(18, 19, 26, 0.9);
  color: white;
  padding: 10px 20px;
  border-radius: 100px;
  font-size: 13px;
  pointer-events: none;
  z-index: 2000;
}

/* ── 트랜지션 ────────────────────────────────────────────── */
.sk-fade-enter-active,
.sk-fade-leave-active {
  transition: opacity 0.2s;
}
.sk-fade-enter-from,
.sk-fade-leave-to {
  opacity: 0;
}
.sk-expand-enter-active,
.sk-expand-leave-active {
  transition:
    max-height 0.2s ease,
    opacity 0.2s;
}
.sk-expand-enter-from,
.sk-expand-leave-to {
  max-height: 0;
  opacity: 0;
}
.sk-expand-enter-to,
.sk-expand-leave-from {
  max-height: 400px;
  opacity: 1;
}
.sk-modal-enter-active,
.sk-modal-leave-active {
  transition: opacity 0.2s;
}
.sk-modal-enter-from,
.sk-modal-leave-to {
  opacity: 0;
}
.sk-toast-enter-active,
.sk-toast-leave-active {
  transition:
    opacity 0.3s,
    transform 0.3s;
}
.sk-toast-enter-from,
.sk-toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}
</style>
