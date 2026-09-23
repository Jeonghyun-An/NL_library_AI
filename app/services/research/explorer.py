"""explorer.py — 하위질문 1개를 탐색한다

기존 검색 파이프라인을 그대로 쓰고(논문 스코프) 원문 대목만 남긴 뒤, 그 위에
피인용 가중을 얹는다. 순위 계산은 rank_hits 로 빼서 Milvus 없이 테스트한다.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.book import BookRepository
from schemas.book import ChunkHit
from services.research.scoring import blend_score, impact_per_year, parse_pub_year
from services.research.state import HitRow

log = logging.getLogger(__name__)

# 원문 대목이 아닌 논문 보강 청크의 라벨. 적재(services/ingestion/stages.py
# run_embed_index)는 논문마다 본문 청크 뒤에 보강 청크를 붙이는데, 쪽수를 주지 않아
# 인덱싱 때 page_start 가 0 이 된다(indexer.index_chunks 의 `or 0`). 라벨별 출처는
# services/ingestion/paper_enricher.py 에서 확인했다.
#   [표 설명]   interpret_table — LLM 이 쓴 서술이다. 논문에 없는 문장이다.
#   [그림 설명] describe_figure — VLM 이 쓴 서술이다. 역시 논문에 없다.
#   [키워드]   헤더 추출이 실패하면 generate_keywords(LLM)가 만든다. 청크만 보고는
#              어느 쪽인지 알 수 없고, 목록이라 대목도 아니다.
#   [초록]     extract_abstract 가 본문에서 그대로 떼어 낸 원문이다. 다만 같은 문장이
#              쪽수가 달린 본문 청크에 이미 있다. 또 메타청크처럼 주제형 질의에서 상위를
#              차지해 본문 대목을 밀어낸다.
# 이것들이 근거에 들면 인용칩이 모델이 쓴 문장이나 초록을 원문 대목처럼 "p.0-0" 으로 띄운다.
# [표] 는 남긴다 — _extract_tables 가 추출 본문의 표 마크다운과 그 앞 200자를 그대로
# 담은 원문이고, 적재가 수치 질문용으로 따로 둔 청크라 수치 근거가 된다.
_NON_SOURCE_LABELS = ("[초록] ", "[키워드] ", "[표 설명] ", "[그림 설명] ")


def is_source_passage(chunk: ChunkHit) -> bool:
    """근거로 인용할 수 있는 원문 대목인가. 메타청크와 생성·중복 보강 청크를 뺀다.

    라벨만 보지 않고 쪽수 0 을 함께 요구한다. 보강 청크는 쪽수가 늘 0 이라, 쪽수가
    있는 청크의 같은 글자는 본문에 우연히 나온 것이다. 반대로 쪽수 0 만으로는 가를 수
    없다 — PyMuPDF 쪽 번호(page.number)가 0 부터라 첫 쪽 본문도 0 이고, PDF 없이
    초록을 본문으로 적재한 논문의 본문도 0 이다.
    """
    # chunk_idx == -1 은 카탈로그 메타 청크다("제목: … | 기관: … | 초록: …").
    # doc_type 스칼라가 같아 doc_scope="paper" 를 통과하고, 제목·초록을 품어 주제형
    # 하위질문에서 점수가 오히려 잘 나온다. 그대로 두면 보고서가 서지 덩어리를
    # 발췌로 인용하고 critic 에게도 그게 발췌로 들어간다.
    if chunk.chunk_idx == -1:
        return False
    return not (chunk.page_start == 0 and chunk.text.startswith(_NON_SOURCE_LABELS))


def rank_hits(
    hits: list[HitRow], meta_by_id: dict[str, dict], *,
    citation_weight: float, now_year: int,
) -> list[HitRow]:
    """연간 피인용을 얹은 rank_score 로 다시 정렬한다. 입력은 건드리지 않는다.

    혼합값을 score 에 덮어쓰지 않는 이유: 혼합값은 1.0 을 넘는다. 리랭킹 0.92
    짜리 2024년 논문이 40회 인용됐으면 0.92 * (1 + 0.2*ln(14.33)) = 1.41 이다.
    score 를 유사도로 읽는 쪽은 그대로 "141%" 를 그리고, 생 리랭킹 점수는
    되찾을 길이 없어진다. 정렬은 rank_score 로, 표시는 score 로 한다.
    """
    ranked = []
    for hit in hits:
        meta = meta_by_id.get(hit["book_id"]) or {}
        impact = impact_per_year(
            meta.get("kci_citations"), parse_pub_year(meta.get("pub_date")),
            now_year=now_year,
        )
        row = dict(hit)
        row["rank_score"] = blend_score(hit["score"], impact=impact, weight=citation_weight)
        ranked.append(row)
    ranked.sort(key=lambda r: r["rank_score"], reverse=True)
    return ranked


async def explore(query: str, *, params: dict, db: AsyncSession) -> tuple[list[HitRow], dict[str, dict]]:
    """검색 → 서지 조회 → 피인용 가중 재정렬.

    returns (정렬된 hit 목록, cnts_id → 서지 메타)
    """
    # pipeline 은 reranker(torch) 를 물고 와 모듈 최상단에서 임포트하면 이 파일을
    # 단순히 열기만 해도(rank_hits 만 쓰는 테스트에서도) torch 가 있어야 한다.
    # 기존 코드베이스도 같은 이유로 지연 임포트한다(api/book.py·main.py 참고).
    from services.search.pipeline import search

    # generate_answer=False — 여기서 만든 답변은 전부 버려진다(resp.chunks 만 쓴다).
    # 보고서는 탐색이 끝난 뒤 synthesizer 가 하위질문별로 모은 근거만 받아 절마다 따로
    # 쓴다. 기본 파라미터로도 explore 는 한 잡에 6~24회 도는데, 여기서 생성하면 컨텍스트
    # 예산 10만 토큰짜리 확장+생성이 그 횟수만큼 공유 GPU 를 물고 아무것도 남기지 않는다.
    #
    # use_rewrite=False — 쿼리 재작성은 도서 추천 전용이다. query_rewrite.yaml 의
    # 유사도 규칙이 "제목·저자명은 쿼리에 절대 포함하지 마세요"이고 예시가
    # 채식주의자·카프카·하루키다. 하위질문("부르디외 문화자본론을 적용한 국내 독서격차
    # 연구")을 통과시키면 고유명사가 떨어져 분위기 키워드로 바뀌고, "X 같은 책" 패턴에
    # 걸리면 _enrich_from_db 가 쿼리를 그 책의 themes 로 통째로 갈아버린다. 계획
    # 단계가 이미 검색어로 쓸 수 있는 문장을 내놓는다(research_plan.yaml).
    # 기록도 이쪽이 맞다 — runner 는 검색 직전 문자열을 subq.queries 에 남기므로,
    # 재작성이 켜져 있으면 사용자에게 보이는 탐색 경로와 research_steps.result["queries"]
    # 가 둘 다 실제로 보낸 적 없는 쿼리를 기록해 0건 하위질문을 사후에 진단할 수 없다.
    #
    # use_metadata_filter=False — db 를 넘기면 파이프라인이 도서 검색어용 날짜 필터를
    # LLM 으로 뽑아 pub_date 조건을 건다(metadata_filter.yaml: "YYYY년 단독 → 그 해만").
    # 하위질문의 사건 연도("2006년 도서관법 전부개정의 영향")가 발행연도가 되어 그 뒤에
    # 나온 연구가 전부 빠지고, 그 조건은 탐색 경로 어디에도 남지 않는다. 재작성을 끈
    # 이유(보낸 검색을 그대로 기록해야 진단된다)가 여기에도 그대로 선다.
    #
    # chunk_filter — 원문 대목만 남긴다(is_source_passage). 파이프라인이 top_k 로 자르기
    # 전에 걸러야 걸러진 수만큼 per_subq_top_k 가 줄지 않는다. 논문 검색 화면이 쓰는
    # 라이브 경로라 기본값은 그대로 두고 여기서만 넘긴다.
    resp = await search(
        query, mode="chunk", top_k=params["per_subq_top_k"],
        doc_scope="paper", generate_answer=False, use_rewrite=False,
        use_metadata_filter=False, chunk_filter=is_source_passage, db=db,
    )
    hits: list[HitRow] = [
        {
            "book_id": c.book_id, "chunk_id": c.chunk_id, "text": c.text,
            "page_start": c.page_start, "page_end": c.page_end,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in resp.chunks
    ]
    if not hits:
        return [], {}

    repo = BookRepository(db)
    books = await repo.get_by_cnts_ids(list({h["book_id"] for h in hits}))
    meta_by_id = {
        cnts_id: {
            "title": b.title, "personal_author": b.personal_author,
            "series_title": b.series_title, "vol_issue": b.vol_issue,
            "pub_date": b.pub_date, "kci_citations": b.kci_citations,
            "grade": b.grade,
        }
        for cnts_id, b in books.items()
    }
    # 서지를 못 찾은 청크는 여기서 떨군다. build_evidence 가 meta_by_id 에 없는
    # book_id 를 말없이 버리기 때문에, 그대로 넘기면 근거 수가 조용히 모자라고
    # critic 이 insufficient 를 내 재검색이 상한까지 돌고도 로그에 흔적이 없다.
    # Milvus 에는 있는데 library_catalog 행이 사라진 일이 실제로 있었다
    # (docs/ops/recurring-gotchas.md 9번).
    kept = [h for h in hits if h["book_id"] in meta_by_id]
    if len(kept) < len(hits):
        orphans = sorted({h["book_id"] for h in hits if h["book_id"] not in meta_by_id})
        log.warning(
            "[explore] 서지 없는 청크 %d/%d 건 제외 — cnts_id %s",
            len(hits) - len(kept), len(hits), orphans[:5],
        )
    ranked = rank_hits(
        kept, meta_by_id,
        citation_weight=params["citation_weight"], now_year=datetime.now().year,
    )
    return ranked, meta_by_id
