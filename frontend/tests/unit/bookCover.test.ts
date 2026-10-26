// frontend/tests/unit/bookCover.test.ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { isDrawnCover } from "~/utils/bookCover";

describe("isDrawnCover — 'AI가 … 그려낸 표지' 안내를 붙일지", () => {
  it("AI 가 그린 그림 표지(covers/{id}.jpg)에만 참", () => {
    expect(isDrawnCover("covers/CNTS-00052063987.jpg")).toBe(true);
  });
  it("글자 표지(covers/typo/…)·키 없음(원문 첫 쪽)은 거짓", () => {
    expect(isDrawnCover("covers/typo/CNTS-00051998720.jpg")).toBe(false);
    expect(isDrawnCover(null)).toBe(false);
    expect(isDrawnCover(undefined)).toBe(false);
    expect(isDrawnCover("")).toBe(false);
  });
  it("소장자료 상세는 안내를 isDrawnCover 로 감싼다", () => {
    const page = readFileSync(resolve(__dirname, "../../pages/books/[cnts_id].vue"), "utf-8");
    expect(page).toMatch(/<p v-if="isDrawnCover\(book\.cover_image_key\)" class="dt-cover-note">/);
  });
});
