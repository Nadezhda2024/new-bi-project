-- 1. Слой для сырых данных из API WB
CREATE SCHEMA IF NOT EXISTS staging;

-- 2. Слой для очищенных данных и справочников
CREATE SCHEMA IF NOT EXISTS core;

-- 3. Слой для готовых витрин, к которым подключится Fastboard
CREATE SCHEMA IF NOT EXISTS mart;

-- Проверяем, что всё создалось успешно
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name IN ('staging', 'core', 'mart');

-- Изменяем тип колонок на BIGINT, чтобы они вмещали любые большие ID от Wildberries
ALTER TABLE staging.products ALTER COLUMN nm_id TYPE BIGINT;
ALTER TABLE staging.products ALTER COLUMN imt_id TYPE BIGINT;
ALTER TABLE staging.products ALTER COLUMN subject_id TYPE BIGINT;

-- Проверяем, что типы успешно обновились
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_schema = 'staging' AND table_name = 'products'
  AND column_name IN ('nm_id', 'imt_id', 'subject_id');
