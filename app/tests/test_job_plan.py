"""잡 생성 dry-run 계획 수립 (build_job_plan) 순수 로직 테스트."""


def test_build_job_plan_basic():
    from services.ingestion.job_manager import build_job_plan

    manifest = [
        {"book_id": "A", "object_key": "originals/A/A.pdf", "title": "가"},
        {"book_id": "B", "object_key": "originals/B/B.pdf", "title": "나"},
        {"book_id": "C", "object_key": "originals/C/C.pdf", "title": "다"},
        {"book_id": "D", "object_key": "originals/D/D.pdf", "title": "라"},
        {"book_id": "A", "object_key": "originals/A/A.pdf", "title": "중복"},  # 매니페스트 중복
    ]
    existing_keys = {"originals/A/A.pdf", "originals/B/B.pdf", "originals/C/C.pdf"}  # D는 MinIO 없음
    meta_ids = {"A", "B", "D"}            # C는 PG 메타 없음
    embedded_ids = {"B"}                   # B는 이미 임베딩됨

    items, report = build_job_plan(manifest, existing_keys, meta_ids, embedded_ids)

    item_ids = {it["book_id"] for it in items}
    # A: 정상 / B: 이미 embedded(스킵) / C: 메타없음(스킵) / D: MinIO 없음(스킵)
    assert item_ids == {"A"}
    assert report["total_manifest"] == 5
    assert report["duplicates"] == ["A"]
    assert report["missing_object"] == ["D"]
    assert report["missing_meta"] == ["C"]
    assert report["already_embedded"] == ["B"]
    assert report["to_ingest"] == 1


def test_build_job_plan_reembed_overrides_skip():
    from services.ingestion.job_manager import build_job_plan

    manifest = [{"book_id": "B", "object_key": "originals/B/B.pdf", "title": "나"}]
    items, report = build_job_plan(
        manifest,
        existing_keys={"originals/B/B.pdf"},
        meta_ids={"B"},
        embedded_ids={"B"},
        reembed=True,   # 이미 embedded여도 재인덱싱
    )
    assert {it["book_id"] for it in items} == {"B"}
    assert report["already_embedded"] == []


def test_build_job_plan_item_shape():
    from services.ingestion.job_manager import build_job_plan

    manifest = [{"book_id": "A", "object_key": "originals/A/A.pdf", "title": "가"}]
    items, _ = build_job_plan(manifest, {"originals/A/A.pdf"}, {"A"}, set())
    it = items[0]
    assert it["book_id"] == "A"
    assert it["source_key"] == "originals/A/A.pdf"
    assert it["stage"] == "pending"
    assert it["status"] == "pending"
