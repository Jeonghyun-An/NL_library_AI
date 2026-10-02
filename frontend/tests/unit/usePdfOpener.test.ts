// frontend/tests/unit/usePdfOpener.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { usePdfOpener } from "~/composables/usePdfOpener";
import type { OpenPdfPayload } from "~/types/research";

// useApi 는 Nuxt 런타임 설정을 읽는다 — 여기서는 주소 조립만 흉내 낸다
vi.mock("~/composables/useApi", () => ({
  apiUrl: (path: string) => `/api${path}`,
  apiHeaders: () => ({ "x-session-id": "sid" }),
}));

const target: OpenPdfPayload = { cntsId: "NL123", title: "논문 제목" };

// pdfStatus 는 응답 본문을 읽지 않고 상태만 쓴다
function stubFetch(status: number) {
  const fetchMock = vi.fn().mockResolvedValue({ status });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("usePdfOpener", () => {
  it("파일이 있으면(200) 안내 없이 원문을 연다", async () => {
    stubFetch(200);
    const { pdf, checking, openPdf } = usePdfOpener();
    await expect(openPdf(target)).resolves.toBeNull();
    expect(pdf.value).toEqual(target);
    expect(checking.value).toBe(false);
  });

  it("파일이 없으면(404) 안내 문구를 돌려주고 원문은 열지 않는다", async () => {
    stubFetch(404);
    const { pdf, checking, openPdf } = usePdfOpener();
    await expect(openPdf(target)).resolves.toBe("원문 파일이 없습니다");
    expect(pdf.value).toBeNull();
    expect(checking.value).toBe(false);
  });

  it("확인하는 중에 다시 열면 바로 null 을 돌려주고 두 번 열지 않는다", async () => {
    let respond: (res: { status: number }) => void = () => {};
    const fetchMock = vi.fn().mockReturnValue(
      new Promise((resolve) => {
        respond = resolve;
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { pdf, checking, openPdf } = usePdfOpener();
    const first = openPdf(target);
    expect(checking.value).toBe(true);

    await expect(openPdf({ cntsId: "OTHER", title: "다른 논문" })).resolves.toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(pdf.value).toBeNull();

    respond({ status: 404 });
    await expect(first).resolves.toBe("원문 파일이 없습니다");
    expect(pdf.value).toBeNull();
    expect(checking.value).toBe(false);
  });

  it("closePdf 는 열린 원문을 닫는다", async () => {
    stubFetch(200);
    const { pdf, openPdf, closePdf } = usePdfOpener();
    await openPdf(target);
    expect(pdf.value).toEqual(target);
    closePdf();
    expect(pdf.value).toBeNull();
  });

  it("확인 요청은 도서 아이디를 인코딩한 /books/<id>/pdf 주소로 세션 헤더와 함께 보낸다", async () => {
    const fetchMock = stubFetch(200);
    const { openPdf } = usePdfOpener();
    await openPdf({ cntsId: "a/b c", title: "" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/books/a%2Fb%20c/pdf");
    expect(init.headers).toEqual({ "x-session-id": "sid" });
  });
});
