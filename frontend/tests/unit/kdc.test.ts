// frontend/tests/unit/kdc.test.ts
import { describe, expect, it } from "vitest";
import { KDC_DIVISIONS, KDC_SECTIONS, kdcChip } from "~/utils/kdc";

describe("KDC 표", () => {
  it("강목은 00~99 100개이고 모두 이름이 있다", () => {
    const keys = Object.keys(KDC_DIVISIONS).sort();
    expect(keys).toHaveLength(100);
    expect(keys).toEqual(Array.from({ length: 100 }, (_, i) => String(i).padStart(2, "0")));
    for (const name of Object.values(KDC_DIVISIONS)) expect(name.trim()).not.toBe("");
  });

  it("요목은 3자리 키이고 그 앞 2자리가 강목에 있다", () => {
    for (const key of Object.keys(KDC_SECTIONS)) {
      expect(key).toMatch(/^\d{3}$/);
      expect(KDC_DIVISIONS[key.slice(0, 2)]).toBeDefined();
    }
  });
});

describe("kdcChip — 분류 칩", () => {
  it("요목(3자리)이 표에 있으면 그 이름이다 — 329 는 재정", () => {
    expect(kdcChip("329")).toEqual({ name: "재정", code: "329", title: "도서관 분류(KDC 329)" });
  });

  it("소수점 아래는 이름을 정하지 않는다 — 813.6 은 한국소설, 811.609 는 한국시", () => {
    expect(kdcChip("813.6")?.name).toBe("한국소설");
    expect(kdcChip("811.609")?.name).toBe("한국시");
    expect(kdcChip("813.09")?.code).toBe("813");
  });

  it("요목이 표에 없으면 강목(2자리)으로 대신한다 — 322.83 은 경제학, 350.8 은 행정학", () => {
    expect(kdcChip("322.83")).toEqual({ name: "경제학", code: "322", title: "도서관 분류(KDC 322)" });
    expect(kdcChip("350.8")?.name).toBe("행정학");
    expect(kdcChip("810.906")?.name).toBe("한국문학");
  });

  it("2자리뿐인 값은 강목으로 읽고, 번호도 2자리다", () => {
    expect(kdcChip("32")).toEqual({ name: "경제학", code: "32", title: "도서관 분류(KDC 32)" });
  });

  it("앞뒤 공백·앞의 글자·숫자 형식도 읽는다", () => {
    expect(kdcChip("  329  ")?.name).toBe("재정");
    expect(kdcChip("KDC 811.6")?.name).toBe("한국시");
    expect(kdcChip(329)?.name).toBe("재정");
    expect(kdcChip(813.6)?.name).toBe("한국소설");
  });

  it("비었거나 읽을 수 없으면 null — 칩이 없다", () => {
    expect(kdcChip(null)).toBeNull();
    expect(kdcChip(undefined)).toBeNull();
    expect(kdcChip("")).toBeNull();
    expect(kdcChip("   ")).toBeNull();
    expect(kdcChip("미상")).toBeNull();
    expect(kdcChip("7")).toBeNull();
    expect(kdcChip(".6")).toBeNull();
  });
});
