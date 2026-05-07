-- introduction 컬럼 추가 마이그레이션
-- 실행: psql -U <user> -d <db> -f migrate_add_introduction.sql

ALTER TABLE library_catalog ADD COLUMN IF NOT EXISTS introduction TEXT;
