-- Создаем таблицу для сырых заказов из API WB в схеме staging
CREATE TABLE IF NOT EXISTS staging.orders (
    -- Оригинальные сущности WB, переведенные в удобный lowercase_with_underscores
    srid TEXT,                          -- Уникальный идентификатор строки заказа
    date TIMESTAMP,                     -- Дата и время заказа
    last_change_date TIMESTAMP,          -- Дата и время последнего изменения статуса
    warehouse_name TEXT,                -- Склад отгрузки
    warehouse_type TEXT,                -- Тип склада (FBO/FBS)
    country_name TEXT,                  -- Страна доставки
    oblast_okrug_name TEXT,             -- Округ/Область
    region_name TEXT,                   -- Регион доставки
    supplier_article TEXT,              -- Артикул продавца
    nm_id INT,                          -- Номенклатура WB (id товара)
    barcode TEXT,                       -- Штрихкод товара
    category TEXT,                      -- Категория товара
    subject TEXT,                       -- Предмет товара
    brand TEXT,                         -- Бренд
    tech_size TEXT,                     -- Размер товара
    income_id INT,                      -- ID поставки
    is_supply BOOLEAN,                  -- Договор поставки
    is_realization BOOLEAN,             -- Договор реализации
    total_price NUMERIC(10, 2),         -- Цена до согласованных скидок
    discount_percent INT,               -- Согласованная скидка
    spp NUMERIC(10, 2),                 -- Скидка постоянного покупателя (СПП)
    finished_price NUMERIC(10, 2),      -- Фактическая цена для клиента
    price_with_disc NUMERIC(10, 2),     -- Цена со скидкой продавца
    is_cancel BOOLEAN,                  -- Отменен ли заказ
    cancel_date TIMESTAMP,              -- Дата отмены заказа
    sticker TEXT,                       -- Стиккер для FBS
    g_number TEXT,                      -- Номер заказа
    
    -- Наши технические поля для контроля качества данных
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Когда строка записалась в нашу БД
    _row_hash TEXT,                                  -- Хэш строки для быстрой проверки изменений
    
    -- Создаем составной уникальный ключ, чтобы не плодить дубли при upsert
    CONSTRAINT pk_staging_orders PRIMARY KEY (srid, last_change_date)
);

-- Проверяем, что таблица успешно появилась в схеме
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'staging';
