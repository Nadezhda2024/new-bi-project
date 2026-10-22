-- Таблица для глубокой аналитики остатков (оборачиваемость, дефицит из /products/products)
CREATE TABLE IF NOT EXISTS staging.stock_analytics (
    nm_id BIGINT,
    orders_count INT,
    buyout_count INT,
    stock_count INT,
    turnover_days INT,
    availability_status TEXT,       -- deficient, balanced, nonLiquid и т.д.
    snapshot_date DATE DEFAULT CURRENT_DATE,
    
    _loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    _row_hash TEXT,
    
    CONSTRAINT pk_staging_stock_analytics PRIMARY KEY (nm_id, snapshot_date)
);
