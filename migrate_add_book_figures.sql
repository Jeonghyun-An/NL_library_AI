-- book_figures 테이블 추가 마이그레이션
-- 실행: psql -U <user> -d <db> -f migrate_add_book_figures.sql

CREATE TABLE IF NOT EXISTS book_figures (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id        VARCHAR(64) NOT NULL,
    page_num       INTEGER NOT NULL,
    img_idx        INTEGER NOT NULL,
    minio_key      TEXT NOT NULL,
    before_context TEXT,
    after_context  TEXT,
    created_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_book_figures_book_id ON book_figures (book_id);
