-- themes 컬럼 추가 마이그레이션
-- 실행: psql -U <user> -d <db> -f migrate_add_themes.sql

ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS themes TEXT;
ALTER TABLE book_sections   ADD COLUMN IF NOT EXISTS themes TEXT;
