-- Создаем таблицу для сырых карточек товаров строго по актуальному гайду WB от 2026 года
CREATE TABLE IF NOT EXISTS staging.products (
    nm_id INT PRIMARY KEY,              -- nmID (Уникальный код карточки)
    imt_id INT,                         -- imtID (ID объединения/группы карточек)
    subject_id INT,                     -- subjectID (ID предмета)
    subject_name TEXT,                  -- subjectName (Название подкатегории)
    nm_uuid TEXT,                       -- nmUUID
    vendor_code TEXT,                   -- vendorCode (Артикул продавца)
    brand TEXT,                         -- brand
    title TEXT,                         -- title
    description TEXT,                   -- description
    gtin TEXT,                          -- gtin
    kiz_marked BOOLEAN,                 -- kizMarked (Маркировка "Честный Знак")
    need_kiz BOOLEAN,                   -- needKiz
    created_at TIMESTAMP,               -- createdAt
    updated_at TIMESTAMP,               -- updatedAt
    
    -- Вложенные массивы и новые объекты 2026 года
    photos JSONB,                       -- Массив ссылок на фото/медиа
    dimensions JSONB,                   -- Габариты (length, width, height, weightBrutto)
    characteristics JSONB,              -- Массив характеристик
    sizes JSONB,                        -- Размеры и skus (бар-коды)
    tags JSONB,                         -- Ярлыки/теги карточки
    documents JSONB,                    -- НОВОЕ: Сертификаты, декларации и вердикты модерации
    
    -- Технические поля контроля
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _row_hash TEXT
);

-- Проверка
SELECT table_name FROM information_schema.tables WHERE table_schema = 'staging';
