import os
import hashlib
import json
import logging
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Параметры подключения к локальной БД
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "wb_analytics")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}"

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def generate_row_hash(order_dict):
    """Генерирует стабильный MD5-хэш от содержимого заказа для контроля изменений."""
    encoded = json.dumps(order_dict, sort_keys=True).encode('utf-8')
    return hashlib.md5(encoded).hexdigest()

def insert_orders_to_staging(raw_orders):
    """Трансформирует ключи JSON в lowercase_with_underscores и делает пакетный upsert."""
    if not raw_orders:
        log.warning("⚠️ Нет данных для загрузки в базу")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows_to_insert = []
            
            for o in raw_orders:
                # Генерируем хэш оригинального JSON до наших преобразований
                row_hash = generate_row_hash(o)
                # 3. Страховка для srid (первичного ключа): берем srid, иначе id, иначе gNumber
                srid_key = o.get("srid") or o.get("id") or o.get("gNumber")
                 # -------------------------------
                 # --- ЛОГИРОВАНИЕ АНОМАЛИЙ И ЗАЩИТНЫЙ ПРОПУСК ---
                if not srid_key:
                    log.error(f"❌ АНОМАЛИЯ: Обнаружен заказ без ID в ответе API WB: {o}")
                    continue  # Пропускаем только этот конкретный дефектный объект, чтобы не уронить весь батч
                # -----------------------------------------------
                                # --- ФИКС ОШИБКИ NULL VALUES ---
                # 1. Извлекаем дату создания (приоритет полю "date", иначе "createdAt")
                order_date = o.get("date") or o.get("createdAt")
                
                # 2. Безопасно извлекаем lastChangeDate. Если равен None/null, подставляем дату создания
                last_change_date = o.get("lastChangeDate") or order_date
                
                converted_price = o.get("convertedPrice", 0) / 100 if o.get("convertedPrice") else 0
                
                row = (
                    str(srid_key) if srid_key else None,                  # srid
                    order_date,                                           # date
                    last_change_date,                                     # last_change_date (ТЕПЕРЬ НИКОГДА НЕ NULL)
                    o.get("warehouseName", "Склад FBS"),                 # warehouse_name
                    "FBS",                                               # warehouse_type
                    None,                                                # country_name (нет в этом методе)
                    None,                                                # oblast_okrug_name
                    None,                                                # region_name
                    o.get("supplierArticle"),                            # supplier_article
                    o.get("nmId"),                                       # nm_id
                    o.get("chrtId"),                                     # barcode (или штрихкод размера)
                    None,                                                # category
                    None,                                                # subject
                    None,                                                # brand
                    None,                                                # tech_size
                    None,                                                # income_id
                    None,                                                # is_supply
                    None,                                                # is_realization
                    converted_price,                                     # total_price
                    0,                                                   # discount_percent
                    0,                                                   # spp
                    converted_price,                                     # finished_price
                    converted_price,                                     # price_with_disc
                    False,                                               # is_cancel
                    None,                                                # cancel_date
                    None,                                                # sticker
                    str(o.get("gNumber") or srid_key),                   # g_number
                    row_hash                                             # _row_hash
                )
                rows_to_insert.append(row)

            # Выполняем быструю вставку пачками по 500 строк
            # Если srid и last_change_date совпадают, мы обновляем хэш строки и цену
            log.info(f"💾 Запись {len(rows_to_insert)} строк в staging.orders...")
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO staging.orders (
                    srid, date, last_change_date, warehouse_name, warehouse_type,
                    country_name, oblast_okrug_name, region_name, supplier_article, nm_id,
                    barcode, category, subject, brand, tech_size, income_id,
                    is_supply, is_realization, total_price, discount_percent, spp,
                    finished_price, price_with_disc, is_cancel, cancel_date, sticker,
                    g_number, _row_hash
                ) VALUES %s
                ON CONFLICT (srid, last_change_date) DO UPDATE SET
                    total_price    = EXCLUDED.total_price,
                    finished_price = EXCLUDED.finished_price,
                    _row_hash      = EXCLUDED._row_hash,
                    _loaded_at     = CURRENT_TIMESTAMP
                """,
                rows_to_insert,
                page_size=500
            )
            
        conn.commit()
        log.info("✅ Пакетная загрузка в staging.orders завершена успешно!")
    except Exception as e:
        conn.rollback()
        log.error(f"❌ Критическая ошибка при записи в БД: {e}")
        raise
    finally:
        conn.close()
def insert_sales_to_staging(raw_sales):
    """Трансформирует ключи JSON продаж и делает пакетный upsert в staging.sales."""
    if not raw_sales:
        log.warning("⚠️ Нет данных продаж для загрузки в базу")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows_to_insert = []
            
            for s in raw_sales:
                row_hash = generate_row_hash(s)
                
                sale_id = s.get("saleID")
                
                # Логирование аномалий
                if not sale_id:
                    log.error(f"❌ АНОМАЛИЯ: Обнаружена строка продажи без saleID: {s}")
                    continue
                
                # В отличие от заказов, у продаж цены в API идут сразу в рублях, а не в копейках
                row = (
                    str(sale_id),                                        # sale_id
                    str(s.get("srid")) if s.get("srid") else None,       # srid
                    str(s.get("gNumber")) if s.get("gNumber") else None, # g_number
                    s.get("date"),                                       # date
                    s.get("lastChangeDate") or s.get("date"),            # last_change_date (защита от null)
                    s.get("warehouseName"),                              # warehouse_name
                    s.get("warehouseType"),                              # warehouse_type
                    s.get("countryName"),                                # country_name
                    s.get("oblastOkrugName"),                            # oblast_okrug_name
                    s.get("regionName"),                                 # region_name
                    s.get("supplierArticle"),                            # supplier_article
                    s.get("nmId"),                                       # nm_id
                    s.get("barcode"),                                    # barcode
                    s.get("category"),                                   # category
                    s.get("subject"),                                    # subject
                    s.get("brand"),                                      # brand
                    s.get("techSize"),                                   # tech_size
                    s.get("incomeID"),                                   # income_id
                    s.get("isSupply"),                                   # is_supply
                    s.get("isRealization"),                              # is_realization
                    s.get("totalPrice"),                                 # total_price
                    s.get("discountPercent"),                            # discount_percent
                    s.get("spp"),                                        # spp
                    s.get("paymentSaleAmount"),                          # payment_sale_amount
                    s.get("forPay"),                                     # for_pay
                    s.get("finishedPrice"),                              # finished_price
                    s.get("priceWithDisc"),                              # price_with_disc
                    s.get("sticker"),                                    # sticker
                    row_hash                                             # _row_hash
                )
                rows_to_insert.append(row)

            log.info(f"💾 Запись {len(rows_to_insert)} строк в staging.sales...")
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO staging.sales (
                    sale_id, srid, g_number, date, last_change_date, warehouse_name,
                    warehouse_type, country_name, oblast_okrug_name, region_name,
                    supplier_article, nm_id, barcode, category, subject, brand,
                    tech_size, income_id, is_supply, is_realization, total_price,
                    discount_percent, spp, payment_sale_amount, for_pay, finished_price,
                    price_with_disc, sticker, _row_hash
                ) VALUES %s
                ON CONFLICT (sale_id) DO UPDATE SET
                    last_change_date = EXCLUDED.last_change_date,
                    for_pay          = EXCLUDED.for_pay,
                    finished_price   = EXCLUDED.finished_price,
                    _row_hash        = EXCLUDED._row_hash,
                    _loaded_at       = CURRENT_TIMESTAMP
                """,
                rows_to_insert,
                page_size=500
            )
            
        conn.commit()
        log.info("✅ Пакетная загрузка в staging.sales завершена успешно!")
    except Exception as e:
        conn.rollback()
        log.error(f"❌ Критическая ошибка при записи продаж в БД: {e}")
        raise
    finally:
        conn.close()
def insert_products_to_staging(raw_cards):
    """Пакетная вставка карточек товаров в staging.products с поддержкой JSONB полей."""
    if not raw_cards:
        log.warning("⚠️ Нет карточек товаров для загрузки в базу")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows_to_insert = []
            
            for c in raw_cards:
                row_hash = generate_row_hash(c)
                nm_id = c.get("nmID")
                
                # Защита от аномалий API: проверяем первичный ключ
                if not nm_id:
                    log.error(f"❌ АНОМАЛИЯ: Обнаружена карточка товара без nmID: {c}")
                    continue
                
                # Упаковываем вложенные массивы и объекты в JSON-строки для Postgres JSONB
                photos_json = json.dumps(c.get("photos", []))
                dimensions_json = json.dumps(c.get("dimensions", {}))
                characteristics_json = json.dumps(c.get("characteristics", []))
                sizes_json = json.dumps(c.get("sizes", []))
                tags_json = json.dumps(c.get("tags", []))
                documents_json = json.dumps(c.get("documents", {}))  # Новый объект 2026 года
                
                row = (
                    int(nm_id),                                          # nm_id
                    c.get("imtID"),                                      # imt_id
                    c.get("subjectID"),                                  # subject_id
                    c.get("subjectName"),                                # subject_name
                    c.get("nmUUID"),                                     # nm_uuid
                    c.get("vendorCode"),                                 # vendor_code
                    c.get("brand"),                                      # brand
                    c.get("title"),                                      # title
                    c.get("description"),                                # description
                    c.get("gtin"),                                       # gtin
                    c.get("kizMarked", False),                           # kiz_marked
                    c.get("needKiz", False),                             # need_kiz
                    c.get("createdAt"),                                  # created_at
                    c.get("updatedAt"),                                  # updated_at
                    photos_json,                                         # photos
                    dimensions_json,                                     # dimensions
                    characteristics_json,                                # characteristics
                    sizes_json,                                          # sizes
                    tags_json,                                           # tags
                    documents_json,                                      # documents
                    row_hash                                             # _row_hash
                )
                rows_to_insert.append(row)

            log.info(f"💾 Запись {len(rows_to_insert)} карточек в staging.products...")
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO staging.products (
                    nm_id, imt_id, subject_id, subject_name, nm_uuid, vendor_code,
                    brand, title, description, gtin, kiz_marked, need_kiz,
                    created_at, updated_at, photos, dimensions, characteristics,
                    sizes, tags, documents, _row_hash
                ) VALUES %s
                ON CONFLICT (nm_id) DO UPDATE SET
                    imt_id              = EXCLUDED.imt_id,
                    vendor_code         = EXCLUDED.vendor_code,
                    title               = EXCLUDED.title,
                    brand               = EXCLUDED.brand,
                    description         = EXCLUDED.description,
                    updated_at          = EXCLUDED.updated_at,
                    photos              = EXCLUDED.photos,
                    dimensions          = EXCLUDED.dimensions,
                    characteristics     = EXCLUDED.characteristics,
                    sizes               = EXCLUDED.sizes,
                    documents           = EXCLUDED.documents,
                    _row_hash           = EXCLUDED._row_hash,
                    _loaded_at          = CURRENT_TIMESTAMP
                """,
                rows_to_insert,
                page_size=500
            )
            
        conn.commit()
        log.info("✅ Пакетная загрузка в staging.products завершена успешно!")
    except Exception as e:
        conn.rollback()
        log.error(f"❌ Критическая ошибка при записи карточек в БД: {e}")
        raise
    finally:
        conn.close()
        
def insert_stocks_to_staging(raw_stocks, stock_type):
    """Пакетная вставка физических остатков в staging.stocks (FBO/FBS)"""
    if not raw_stocks:
        log.warning(f"⚠️ Нет данных остатков типа {stock_type} для записи в БД")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows_to_insert = []
            for s in raw_stocks:
                row_hash = generate_row_hash(s)
                chrt_id = s.get("chrtId")
                warehouse_id = s.get("warehouseId")
                
                if not chrt_id or warehouse_id is None:
                    continue
                
                row = (
                    s.get("nmId"),
                    int(chrt_id),
                    int(warehouse_id),
                    s.get("warehouseName", "Неизвестный склад"),
                    s.get("regionName", "Неизвестный регион"),
                    int(s.get("quantity", 0)),
                    int(s.get("inWayToClient", 0)),
                    int(s.get("inWayFromClient", 0)),
                    stock_type
                )
                rows_to_insert.append((*row, row_hash))

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO staging.stocks (
                    nm_id, chrt_id, warehouse_id, warehouse_name, region_name,
                    quantity, in_way_to_client, in_way_from_client, stock_type, _row_hash
                ) VALUES %s
                ON CONFLICT (chrt_id, warehouse_id, snapshot_date) DO UPDATE SET
                    quantity           = EXCLUDED.quantity,
                    in_way_to_client   = EXCLUDED.in_way_to_client,
                    in_way_from_client = EXCLUDED.in_way_from_client,
                    _row_hash          = EXCLUDED._row_hash,
                    _loaded_at         = CURRENT_TIMESTAMP
                """,
                rows_to_insert, page_size=500
            )
        conn.commit()
        log.info(f"✅ Физические остатки ({stock_type}) успешно сохранены.")
    except Exception as e:
        conn.rollback()
        log.error(f"❌ Ошибка записи физических остатков: {e}")
        raise
    finally:
        conn.close()


def insert_stock_analytics_to_staging(raw_items):
    """Пакетная вставка бизнес-показателей товара в staging.stock_analytics"""
    if not raw_items:
        log.warning("⚠️ Нет аналитических данных по товарам для записи")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            rows_to_insert = []
            for item in raw_items:
                row_hash = generate_row_hash(item)
                nm_id = item.get("nmID")
                metrics = item.get("metrics", {})
                
                if not nm_id:
                    continue
                
                turnover_days = metrics.get("avgStockTurnover", {}).get("days", 0)
                
                row = (
                    int(nm_id),
                    int(metrics.get("ordersCount", 0)),
                    int(metrics.get("buyoutCount", 0)),
                    int(metrics.get("stockCount", 0)),
                    int(turnover_days),
                    metrics.get("availability", "unknown")
                )
                rows_to_insert.append((*row, row_hash))

            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO staging.stock_analytics (
                    nm_id, orders_count, buyout_count, stock_count, turnover_days, availability_status, _row_hash
                ) VALUES %s
                ON CONFLICT (nm_id, snapshot_date) DO UPDATE SET
                    orders_count        = EXCLUDED.orders_count,
                    buyout_count        = EXCLUDED.buyout_count,
                    stock_count         = EXCLUDED.stock_count,
                    turnover_days       = EXCLUDED.turnover_days,
                    availability_status = EXCLUDED.availability_status,
                    _row_hash           = EXCLUDED._row_hash,
                    _loaded_at          = CURRENT_TIMESTAMP
                """,
                rows_to_insert, page_size=500
            )
        conn.commit()
        log.info("✅ Глубокая аналитика остатков успешно сохранена.")
    except Exception as e:
        conn.rollback()
        log.error(f"❌ Ошибка записи аналитики остатков: {e}")
        raise
    finally:
        conn.close()


def get_catalog_ids_for_stocks():
    """Вытаскивает списки nm_id и chrt_id из загруженного каталога товаров."""
    conn = get_db_connection()
    nm_ids, chrt_ids = [], []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT nm_id, (size_elem->>'chrtID')::BIGINT
                FROM staging.products,
                jsonb_array_elements(sizes) AS size_elem
                WHERE size_elem->>'chrtID' IS NOT NULL;
            """)
            for row in cur.fetchall():
                nm_ids.append(int(row[0]))
                chrt_ids.append(int(row[1]))
    finally:
        conn.close()
    return list(set(nm_ids)), list(set(chrt_ids))
