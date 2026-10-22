-- Создаем единую таблицу остатков для FBO (склады WB) и FBS (склады продавца)
CREATE TABLE IF NOT EXISTS staging.stocks (
    nm_id BIGINT,                       -- nmId
    chrt_id BIGINT,                     -- chrtId
    warehouse_id BIGINT,                -- warehouseId (для WB складов это будут минусовые ID или реальные коды)
    warehouse_name TEXT,                -- warehouseName (например, Подольск, Коледино или Твой Склад)
    region_name TEXT,                   -- regionName (Федеральный округ/Регион для гео-аналитики)
    quantity INT,                       -- quantity (Текущий свободный остаток)
    in_way_to_client INT DEFAULT 0,     -- inWayToClient (Товары в пути к покупателю, только для FBO)
    in_way_from_client INT DEFAULT 0,   -- inWayFromClient (Товары на возврате от покупателя, только для FBO)
    stock_type TEXT,                    -- Техническое поле: 'wb' (FBO) или 'seller' (FBS)
    snapshot_date DATE DEFAULT CURRENT_DATE, -- Дата снимка (каждый день создается новый срез остатков)
    
    -- Технические поля контроля
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _row_hash TEXT,
    
    -- Первичный ключ: один артикул на одном складе в один конкретный день имеет только одну уникальную строчку
    CONSTRAINT pk_staging_stocks PRIMARY KEY (chrt_id, warehouse_id, snapshot_date)
);

-- Проверяем создание
SELECT table_name FROM information_schema.tables WHERE table_schema = 'staging';
