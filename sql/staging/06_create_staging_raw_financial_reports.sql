-- Скрипт создания таблицы сырых данных в схеме staging
-- Ветка: feature/sql-tables

CREATE TABLE IF NOT EXISTS staging.raw_financial_reports (
    raw_id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE,
    
    realizationreport_id BIGINT,          
    srv_distrib_date TIMESTAMP WITH TIME ZONE, 
    date_from TIMESTAMP WITH TIME ZONE,     
    date_to TIMESTAMP WITH TIME ZONE,       
    
    rrd_id BIGINT,                         
    gi_id BIGINT,                          
    subject_name VARCHAR(255),             
    nm_id BIGINT,                          
    brand_name VARCHAR(255),               
    sa_name VARCHAR(255),                  
    ts_name VARCHAR(50),                   
    barcode VARCHAR(50),                   
    doc_type_name VARCHAR(100),            
    
    quantity INT,                          
    retail_price NUMERIC(12, 2),           
    retail_amount NUMERIC(12, 2),          
    sale_percent NUMERIC(5, 2),            
    commission_percent NUMERIC(5, 2),      
    office_name VARCHAR(255),              
    supplier_oper_name VARCHAR(255),       
    
    retail_price_with_disc_rub NUMERIC(12, 2), 
    ppvz_for_pay NUMERIC(12, 2),           
    ppvz_vw NUMERIC(12, 2),                
    ppvz_vw_nds NUMERIC(12, 2),            
    
    delivery_amount INT,                   
    return_amount INT,                     
    delivery_rub NUMERIC(12, 2),           
    gi_box_type_name VARCHAR(100),         
    product_id BIGINT,                     
    rid BIGINT,                            
    spp NUMERIC(5, 2),                     
    
    penalty_rub NUMERIC(12, 2),            
    additional_payment NUMERIC(12, 2),     
    rebate_regular_valid_rub NUMERIC(12, 2), 
    storage_fee NUMERIC(12, 2),            
    acceptance_fee NUMERIC(12, 2),         
    
    declaration_number VARCHAR(255),       
    sticker_id VARCHAR(100),               
    site_country VARCHAR(100)              
);

-- Индексы с указанием схемы staging
CREATE INDEX IF NOT EXISTS idx_raw_fin_report_id ON staging.raw_financial_reports(realizationreport_id);
CREATE INDEX IF NOT EXISTS idx_raw_fin_nm_id ON staging.raw_financial_reports(nm_id);
CREATE INDEX IF NOT EXISTS idx_raw_fin_rrd_id ON staging.raw_financial_reports(rrd_id);
