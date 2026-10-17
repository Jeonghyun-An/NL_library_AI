// frontend/tests/unit/adminJobs.test.ts
// 관리자 잡 화면(pages/admin/jobs.vue)의 오류 처리(에러 처리 2단계 — 공통 영역). 읽기 실패가 처리되지 않은 Promise 거부로 5초마다 쌓이던 것,
// 제어·재시도 실패에 안내가 없던 것, 재시도 연타, 잡 생성 뒤 목록 읽기 실패가 '실패'로 보이던 것(다시 눌러 같은 잡이 또 생김)을 지킨다.
// 마운트 도구가 없어 소스 글로 지킨다
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const src = readFileSync(fileURLToPath(new URL("../../pages/admin/jobs.vue", import.meta.url)), "utf-8").replace(
  /\r\n/g,
  "\n",
);
const js = src.slice(src.indexOf("<script setup"), src.indexOf("</script>"));
const tpl = src.slice(src.indexOf("<template>"), src.lastIndexOf("</template>"));

/** function name(...) { … } 본문 — 다음 최상위 함수·선언 앞까지 */
function fnBody(name: string): string {
  const start = js.search(new RegExp(`(?:async )?function ${name}\\(`));
  expect(start, name).toBeGreaterThanOrEqual(0);
  const rest = js.slice(start);
  const end = rest.slice(1).search(/\n(?:async function|function|const|let|onMounted|onUnmounted)\b/);
  return end < 0 ? rest : rest.slice(0, end + 1);
}

describe("관리자 잡 화면 — 읽기 실패", () => {
  it("목록·상세 읽기는 잡아서 그 칸에 알리고 던지지 않는다(늦은 응답은 버린다)", () => {
    const jobs = fnBody("loadJobs");
    expect(jobs).toMatch(/const seq = \+\+jobsSeq;/);
    expect(jobs).toMatch(/catch \(e\) \{\s*if \(seq !== jobsSeq\) return;\s*jobsError\.value = apiErrorMessage\(e, "잡 목록을 불러오지 못했어요"\);/);
    const detail = fnBody("loadDetail");
    expect(detail).toMatch(/const seq = \+\+detailSeq;/);
    expect(detail).toMatch(/catch \(e\) \{\s*if \(seq !== detailSeq\) return;\s*detailError\.value = apiErrorMessage\(e, "잡 상세를 불러오지 못했어요"\);/);
  });

  it("읽기에는 시간 제한을 둔다", () => {
    expect(js).toContain("const READ = { timeout: API_READ_TIMEOUT_MS } as const;");
    expect(fnBody("loadJobs")).toContain("$fetch<{ jobs: Job[] }>(api, READ)");
    expect(fnBody("loadDetail")).toContain("$fetch<JobDetail>(`${api}/${id}`, READ)");
  });

  it("폴링은 앞 폴링이 끝나야 다음을 보낸다", () => {
    expect(fnBody("poll")).toMatch(/if \(polling\) return;\s*polling = true;\s*try \{\s*await Promise\.all\(\[loadJobs\(\), loadDetail\(\)\]\);\s*\} finally \{\s*polling = false;/);
    expect(js).toContain("pollTimer = setInterval(() => void poll(), 5000);");
  });

  it("못 읽은 것을 '잡이 없어요'로 보이지 않는다 — 목록을 받은 뒤·오류가 없을 때만", () => {
    expect(tpl).toMatch(/<li v-if="jobsLoaded && !jobs.length && !jobsError"[^>]*>\s*잡이 없어요\s*<\/li>/);
    expect(tpl).toMatch(/<p v-if="jobsError" role="alert" :class="\[ERROR_LINE, 'mb-2'\]">\{\{ jobsError \}\}<\/p>/);
    expect(tpl).toMatch(/<p v-if="detailError" role="alert" :class="ERROR_LINE">\{\{ detailError \}\}<\/p>/);
    expect(tpl).toMatch(/<div v-if="!selectedId"[^>]*>\s*잡을 선택해 주세요\s*<\/div>/);
    expect(tpl).not.toContain("잡 없음");
    expect(tpl).not.toContain("잡을 선택하세요");
  });

  it("잡을 바꾸면 이전 잡의 상세·오류를 비우고 읽는다", () => {
    expect(fnBody("selectJob")).toMatch(/if \(selectedId\.value !== id\) \{\s*\/\/[^\n]*\n\s*detail\.value = null;\s*failures\.value = \[\];\s*detailError\.value = "";/);
  });
});

describe("관리자 잡 화면 — 제어·재시도", () => {
  it("제어 실패를 알리고, 제어가 된 뒤의 다시 읽기 실패는 제어 실패로 보이지 않는다", () => {
    const body = fnBody("control");
    expect(body).toMatch(
      /try \{\s*await \$fetch\(`\$\{api\}\/\$\{id\}\/\$\{action\}`, \{ method: "POST" \}\);\s*\} catch \(e\) \{\s*if \(selectedId\.value === id\) controlError\.value = apiErrorMessage\(e, `잡을 \$\{CONTROL_LABEL\[action\] \?\? action\}하지 못했어요`\);\s*return;\s*\} finally \{\s*loading\.value = false;\s*\}/,
    );
    expect(body.indexOf("await Promise.all([loadJobs(), loadDetail()])")).toBeGreaterThan(body.indexOf("} finally {"));
    expect(tpl).toContain('<p v-if="controlError" role="alert" :class="[ERROR_LINE, \'mb-4\']">{{ controlError }}</p>');
  });

  it("재시도는 도는 동안 다시 보내지 않고(버튼도 막는다), 실패를 알린다", () => {
    const body = fnBody("sendRetry");
    expect(body).toMatch(/if \(!id \|\| retrying\.value\) return;\s*retrying\.value = key;/);
    expect(body).toMatch(/catch \(e\) \{\s*if \(selectedId\.value === id\) retryError\.value = apiErrorMessage\(e, "재시도하지 못했어요"\);\s*return;\s*\} finally \{\s*retrying\.value = null;/);
    expect(tpl).toMatch(/@click="retryAllFailed"\s+:disabled="!!retrying"/);
    expect(tpl).toMatch(/@click="retryGroup\(g\.error_group\)"\s+:disabled="!!retrying"/);
    expect(tpl).toContain('<p v-if="retryError" role="alert" :class="[ERROR_LINE, \'mb-3\']">{{ retryError }}</p>');
  });

  it("응답을 기다리는 사이 다른 잡을 고르면 늦게 온 실패를 새 잡 자리에 쓰지 않는다 — 보낼 때 잡은 id 로 견준다", () => {
    for (const name of ["control", "sendRetry"]) {
      const body = fnBody(name);
      expect(body, name).toMatch(/const id = selectedId\.value;/);
      // catch 안의 오류 쓰기는 모두 id 비교 뒤에만
      const catchBody = body.slice(body.indexOf("} catch (e) {"), body.indexOf("} finally {"));
      expect(catchBody, name).toMatch(/if \(selectedId\.value === id\) \w+Error\.value = /);
      expect(catchBody.match(/Error\.value = /g), name).toHaveLength(1);
    }
    // 잡을 바꾸면 제어·재시도 오류 칸도 비운다
    expect(fnBody("selectJob")).toMatch(/controlError\.value = "";\s*retryError\.value = "";/);
  });
});

describe("관리자 잡 화면 — 잡 생성", () => {
  it("생성이 된 뒤의 목록 읽기는 생성 실패로 떨어지지 않는다 — '생성됨'을 남긴다", () => {
    const body = fnBody("createJob");
    const catchAt = body.indexOf("} catch (e) {");
    expect(catchAt).toBeGreaterThan(0);
    expect(body.indexOf("createMsg.value = `생성됨:")).toBeGreaterThan(catchAt);
    expect(body.indexOf("await loadJobs();")).toBeGreaterThan(body.indexOf("createMsg.value = `생성됨:"));
    expect(body).toMatch(/catch \(e\) \{\s*createError\.value = createErrorMessage\(e\);\s*return;/);
  });

  it("영문 e.message 는 보이지 않는다 — 서버 사유 문자열이 없으면 apiErrorMessage", () => {
    const code = js.replace(/\/\/[^\n]*/g, "");
    expect(code).not.toMatch(/e\??\.message/);
    const body = fnBody("createErrorMessage");
    // 서버의 '잡 생성 실패: …'(한글이 든 문자열 detail)만 그대로 — 프레임워크의 영문 detail 은 apiErrorMessage 로
    expect(body).toContain('typeof detail === "string" && /[가-힣]/.test(detail) ? detail.trim() : apiErrorMessage(e, "잡을 만들지 못했어요")');
    expect(tpl).toContain('<p v-if="createError" role="alert" :class="ERROR_LINE">{{ createError }}</p>');
  });

  it("오류 줄은 빨간 글이 아니다", () => {
    expect(js).toMatch(/const ERROR_LINE = "text-xs text-gray-700 [^"]*whitespace-pre-line";/);
    expect(js.match(/const ERROR_LINE = "([^"]*)"/)?.[1]).not.toMatch(/red|rose/);
    // 오류 줄은 모두 이 모양을 쓴다(상태 배지의 rose 는 잡 상태 'canceled' 의 색이라 오류 글이 아니다)
    expect((tpl.match(/role="alert"/g) ?? []).length).toBe((tpl.match(/role="alert" :class="(?:ERROR_LINE|\[ERROR_LINE, '[\w-]+'\])"/g) ?? []).length);
  });
});
