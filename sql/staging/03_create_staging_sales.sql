-- Создаем таблицу для сырых продаж из API Статистики WB
CREATE TABLE IF NOT EXISTS staging.sales (
    sale_id TEXT,                       -- saleID
    srid TEXT,                          -- srid
    g_number TEXT,                      -- gNumber
    date TIMESTAMP,                     -- date
    last_change_date TIMESTAMP,         -- lastChangeDate
    warehouse_name TEXT,                -- warehouseName
    warehouse_type TEXT,                -- warehouseType
    country_name TEXT,                  -- countryName
    oblast_okrug_name TEXT,             -- oblastOkrugName
    region_name TEXT,                   -- regionName
    supplier_article TEXT,              -- supplierArticle
    nm_id INT,                          -- nmId
    barcode TEXT,                       -- barcode
    category TEXT,                      -- category
    subject TEXT,                       -- subject
    brand TEXT,                         -- brand
    tech_size TEXT,                     -- techSize
    income_id INT,                      -- incomeID
    is_supply BOOLEAN,                  -- isSupply
    is_realization BOOLEAN,             -- isRealization
    total_price NUMERIC(10, 2),         -- totalPrice
    discount_percent INT,               -- discountPercent
    spp NUMERIC(10, 2),                 -- spp
    payment_sale_amount INT,            -- paymentSaleAmount
    for_pay NUMERIC(10, 2),             -- forPay
    finished_price NUMERIC(10, 2),      -- finishedPrice
    price_with_disc NUMERIC(10, 2),     -- priceWithDisc
    sticker TEXT,                       -- sticker
    
    -- Технические поля контроля аналитика
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _row_hash TEXT,
    
    -- Уникальный ключ для слоя staging (каждая транзакция продажи/возврата уникальна по saleID)
    CONSTRAINT pk_staging_sales PRIMARY KEY (sale_id)
);

-- Проверка создания
SELECT table_name FROM information_schema.tables WHERE table_schema = 'staging';
