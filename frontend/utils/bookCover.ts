// frontend/utils/bookCover.ts
// 소장자료 표지의 종류. 화면의 표지(/api/books/{id}/thumbnail)는 library_catalog.cover_image_key 가 있으면 그 그림을, 없으면 원문
// 첫 쪽(PDF 1p)을 보인다(app/api/book.py get_book_thumbnail). 키는 AI 가 그린 그림 표지 covers/{id}.jpg, 글자로 짠 목업 표지
// covers/typo/{id}.jpg 두 가지다(app/services/ingestion/cover_generator.py cover_key).

/** AI 가 그린 그림 표지인지 — 상세의 'AI가 도서 내용을 분석해 그려낸 표지입니다' 안내는 이때만 붙인다. 원문 첫 쪽이나 글자 표지에
 *  붙으면 사실과 다르다(사용자 2026-10-26: 재적재한 소장자료는 표지가 원문 첫 쪽인데 안내가 붙어 있었다) */
export function isDrawnCover(key: string | null | undefined): boolean {
  return !!key && !key.includes("/typo/");
}
