import time
import sys
import os
from datetime import date, timedelta

# Имитируем заглушки функций базы данных для Этапа 1
def insert_products_to_staging_mock(data): print(f"[DB MOCK] Отправлено в staging.products: {len(data)} строк")
def insert_orders_to_staging_mock(data): print(f"[DB MOCK] Отправлено в staging.orders: {len(data)} строк")
def insert_sales_to_staging_mock(data): print(f"[DB MOCK] Отправлено в staging.sales: {len(data)} строк")
def insert_stocks_to_staging_mock(data, mode): print(f"[DB MOCK] Отправлено в staging.stocks ({mode}): {len(data)} строк")
def insert_stock_analytics_to_staging_mock(data): print(f"[DB MOCK] Отправлено в staging.stock_analytics: {len(data)} строк")

# Подключаем наш wb_client из папки scripts
ROOT_DIR = r"D:\Documents\Dev\projects\new-bi-project"
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from scripts.wb_client import (
    write_json_log,
    fetch_content_products_raw,
    fetch_analytics_wb_stocks_raw,
    fetch_analytics_seller_stocks_raw,
    fetch_analytics_products_business_raw,
    safe_request,
    WB_TOKEN_STAT
)

def run_pipeline_optimized_test():
    pipeline_session_id = "pipeline-session-test"
    write_json_log("INFO", pipeline_session_id, "PIPELINE", "START", message="Запуск оптимизированного пайплайна")
    start_time = time.time()
    
    try:
        # 1. Выгрузка каталога товаров (1 запрос)
        write_json_log("INFO", pipeline_session_id, "PIPELINE", "CATALOG_START", message="Выгрузка карточек товаров")
        raw_cards = fetch_content_products_raw()
        insert_products_to_staging_mock(raw_cards)
        
        # Пересчитываем дату для Статистики (один запрос на 5 дней назад)
        start_date_str = f"{(date.today() - timedelta(days=5)).isoformat()}T00:00:00"
        headers_stat = {"Authorization": WB_TOKEN_STAT}
        
        # 2. Выгрузка ЗАКАЗОВ пакетом (1 запрос вместо 6)
        write_json_log("INFO", pipeline_session_id, "PIPELINE", "ORDERS_START", message="Выгрузка заказов единым пакетом")
        url_orders = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
        resp_orders = safe_request("GET", url_orders, headers=headers_stat, params={"dateFrom": start_date_str, "flag": 1}, timeout=120)
        raw_orders = resp_orders.json() if isinstance(resp_orders.json(), list) else []
        insert_orders_to_staging_mock(raw_orders)
        
        # Ждем 60 секунд ОДИН раз, чтобы гарантированно очистить окно лимита для следующего метода статистики
        write_json_log("INFO", pipeline_session_id, "PIPELINE", "WAIT_LIMIT", message="Пауза 60 сек для очистки лимита статистики перед продажами")
        time.sleep(60.0)
        
        # 3. Выгрузка ПРОДАЖ пакетом (1 запрос вместо 6)
        write_json_log("INFO", pipeline_session_id, "PIPELINE", "SALES_START", message="Выгрузка продаж единым пакетом")
        url_sales = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
        resp_sales = safe_request("GET", url_sales, headers=headers_stat, params={"dateFrom": start_date_str, "flag": 1}, timeout=120)
        raw_sales = resp_sales.json() if isinstance(resp_sales.json(), list) else []
        insert_sales_to_staging_mock(raw_sales)
        
        # 4. Выгрузка остатков и аналитики (FBO + FBS + Тренды v2)
        nm_ids = list(set([card.get("nmID") for card in raw_cards if card.get("nmID")]))
        chrt_ids = []
        for card in raw_cards:
            for size in card.get("sizes", []):
                c_id = size.get("chrtID")
                if c_id:
                    chrt_ids.append(c_id)
        chrt_ids = list(set(chrt_ids))
        
        if not nm_ids:
            write_json_log("WARNING", pipeline_session_id, "PIPELINE", "CATALOG_EMPTY", message="Каталог пуст")
        else:
            # Выгрузка FBO (Склады WB)
            write_json_log("INFO", pipeline_session_id, "PIPELINE", "STOCKS_FBO_START", message="Выгрузка остатков FBO")
            raw_wb = fetch_analytics_wb_stocks_raw(nm_ids, chrt_ids)
            insert_stocks_to_staging_mock(raw_wb, "wb")
            
            time.sleep(1.0)
            
            # Выгрузка FBS (Склады продавца)
            write_json_log("INFO", pipeline_session_id, "PIPELINE", "STOCKS_FBS_START", message="Выгрузка остатков FBS")
            raw_seller = fetch_analytics_seller_stocks_raw(nm_ids, chrt_ids)
            insert_stocks_to_staging_mock(raw_seller, "seller")
            
            time.sleep(1.0)
            
            # Выгрузка глубокой бизнес-аналитики
            write_json_log("INFO", pipeline_session_id, "PIPELINE", "BUSINESS_ANALYTICS_START", message="Выгрузка бизнес-аналитики остатков")
            raw_business = fetch_analytics_products_business_raw(nm_ids)
            insert_stock_analytics_to_staging_mock(raw_business)
        
        duration = time.time() - start_time
        write_json_log("INFO", pipeline_session_id, "PIPELINE", "SUCCESS", message=f"Оптимизированный пайплайн выполнен за {duration:.2f} сек")
        
    except Exception as e:
        write_json_log("CRITICAL", pipeline_session_id, "PIPELINE", "FAILED", error=str(e), message="Пайплайн упал")

# Запуск
run_pipeline_test = run_pipeline_optimized_test()
