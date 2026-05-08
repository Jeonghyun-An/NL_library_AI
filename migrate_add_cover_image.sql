-- library_catalog: 자동 생성 표지 정보 컬럼 추가
-- 실행: psql -U <user> -d <db> -f migrate_add_cover_image.sql

ALTER TABLE library_catalog
    ADD COLUMN IF NOT EXISTS cover_image_key VARCHAR(256);

ALTER TABLE library_catalog
    ADD COLUMN IF NOT EXISTS cover_prompt TEXT;
