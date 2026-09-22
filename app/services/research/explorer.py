"""explorer.py — 하위질문 1개를 탐색한다

기존 검색 파이프라인을 그대로 쓰고(논문 스코프), 그 위에 피인용 가중만
얹는다. 순위 계산은 rank_hits 로 빼서 Milvus 없이 테스트한다.
"""
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.book import BookRepository
from services.research.scoring import blend_score, impact_per_year, parse_pub_year
from services.research.state import HitRow

log = logging.getLogger(__name__)


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
    # 보고서는 마지막에 근거 전체로 한 번 종합한다. 기본 파라미터로도 explore 는 한
    # 잡에 6~24회 도는데, 하위질문마다 생성하면 컨텍스트 예산 10만 토큰짜리 확장+생성이
    # 그 횟수만큼 공유 GPU 를 물고 아무것도 남기지 않는다.
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
    resp = await search(
        query, mode="chunk", top_k=params["per_subq_top_k"],
        doc_scope="paper", generate_answer=False, use_rewrite=False, db=db,
    )
    # chunk_idx == -1 은 카탈로그 메타 청크다("제목: … | 기관: … | 초록: …").
    # doc_type 스칼라가 같아 doc_scope="paper" 를 통과하고 제목·초록을 품고 있어
    # 주제형 하위질문에서 점수가 오히려 잘 나온다. 그대로 두면 보고서가 서지 덩어리를
    # "논문 발췌 (p.0-0)" 로 인용하고(page_start 가 없어 인덱싱 때 0 이 된다)
    # critic 에게도 그게 발췌로 들어간다. chunk 모드는 논문 검색 화면이 쓰는 라이브
    # 경로라 파이프라인은 건드리지 않고 여기서만 걸러낸다(도서 모드는 이미 제외한다).
    hits: list[HitRow] = [
        {
            "book_id": c.book_id, "chunk_id": c.chunk_id, "text": c.text,
            "page_start": c.page_start, "page_end": c.page_end,
            "score": c.rerank_score if c.rerank_score is not None else c.score,
        }
        for c in resp.chunks
        if c.chunk_idx != -1
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
