import logging
import time
from scripts.wb_client import (
    fetch_content_products_raw,
    fetch_marketplace_orders_raw,
    fetch_marketplace_sales_raw,
    fetch_analytics_wb_stocks_raw,
    fetch_analytics_seller_stocks_raw,
    fetch_analytics_products_business_raw
)
from scripts.db_loader import (
    insert_products_to_staging,
    insert_orders_to_staging,
    insert_sales_to_staging,
    insert_stocks_to_staging,
    insert_stock_analytics_to_staging,
    get_catalog_ids_for_stocks
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def run_pipeline():
    log.info("🚀 Запуск комплексного ETL-пайплайна WB (Раздельное хранение остатков и аналитики)")
    start_time = time.time()
    
    try:
        log.info("--- [1/4] Выгрузка карточек товаров ---")
        raw_cards = fetch_content_products_raw()
        insert_products_to_staging(raw_cards)
        time.sleep(2)
        
        log.info("--- [2/4] Выгрузка заказов ---")
        raw_orders = fetch_marketplace_orders_raw()
        insert_orders_to_staging(raw_orders)
        time.sleep(2)
        
        log.info("--- [3/4] Выгрузка продаж ---")
        raw_sales = fetch_marketplace_sales_raw()
        insert_sales_to_staging(raw_sales)
        time.sleep(2)
        
        # --- [4/4] Сбор данных остатков (FBO + FBS + Тренды v2) ---
        nm_ids, chrt_ids = get_catalog_ids_for_stocks()
        
        if not nm_ids:
            log.warning("⚠️ Каталог пуст. Невозможно запросить остатки.")
        else:
            # 1. Запрос физических остатков WB (FBO) -> едет в staging.stocks
            raw_wb = fetch_analytics_wb_stocks_raw(nm_ids, chrt_ids)
            insert_stocks_to_staging(raw_wb, "wb")
            
            # Спим 25 секунд, чтобы очистить окно лимитов API WB (Burst Rate)
            log.info("⏳ Пауза 25 секунд для соблюдения лимитов API Аналитики...")
            time.sleep(25)
            
            # 2. Запрос физических остатков продавца (FBS) -> едет в staging.stocks
            raw_seller = fetch_analytics_seller_stocks_raw(nm_ids, chrt_ids)
            insert_stocks_to_staging(raw_seller, "seller")
            
            # Спим еще 25 секунд перед вызовом финального метода
            log.info("⏳ Пауза 25 секунд для соблюдения лимитов API Аналитики...")
            time.sleep(25)
            
            # 3. Запрос глубокой аналитики WB -> едет в staging.stock_analytics
            raw_business = fetch_analytics_products_business_raw(nm_ids)
            insert_stock_analytics_to_staging(raw_business)
        
        log.info(f"🎉 Профессиональный пайплайн успешно выполнен за {time.time() - start_time:.2f} сек!")
    except Exception as e:
        log.error(f"🚨 Работа пайплайна аварийно прервана: {e}")

if __name__ == "__main__":
    run_pipeline()
