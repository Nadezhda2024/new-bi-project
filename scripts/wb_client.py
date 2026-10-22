import os
import time
import random
import logging
from datetime import datetime, date, timedelta
import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# Для этого метода нужен токен СТАТИСТИКИ
WB_TOKEN_STAT = os.getenv("WB_TOKEN_STATISTICS")

def safe_request(url, headers=None, params=None, timeout=60, max_retries=3):
    """Безопасный GET-запрос с обработкой лимитов (429) и сетевых ошибок."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=timeout)
            if resp.status_code != 429:
                return resp
            
            print(f"⚠️ 429 Лимит API (попытка {attempt+1}/{max_retries})")
            retry_after = resp.headers.get('X-Ratelimit-Retry')
            
            if retry_after:
                wait = int(retry_after) + random.uniform(0.5, 1.5)
            else:
                wait = 60  # Жесткий лимит статистики WB — 1 запрос в минуту
            
            print(f"   ⏳ Ждем {wait:.1f} сек по требованию лимитов...")
            time.sleep(wait)
            
        except Exception as e:
            print(f"⚠️ Сетевая ошибка: {e}. Повтор через 5 сек...")
            time.sleep(5)
    
    raise Exception(f"❌ Не удалось получить данные после {max_retries} попыток")

def fetch_marketplace_orders_raw():
    """
    Запрашивает заказы из API Статистики WB за последние 90 дней.
    Использует формат даты RFC3339 и flag=1 для безопасного скачивания.
    """
    if not WB_TOKEN_STAT:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_STATISTICS")

    headers = {"Authorization": WB_TOKEN_STAT}
    all_orders = []
    
    # Официальный эндпоинт из твоей документации
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    
    # Выгружаем историю за 90/5 дней (максимум для этого метода)
    start_date = date.today() - timedelta(days=5)
    end_date = date.today()

    log.info(f"🛰️ Запрос заказов из API Статистики WB с {start_date} по {end_date}")

    current_date = start_date
    while current_date <= end_date:
        # Форматируем дату строго в RFC3339, как требует WB: YYYY-MM-DD
        # Для flag=1 время значения не имеет, передаем начало дня
        date_from_str = f"{current_date.isoformat()}T00:00:00"
        
        log.info(f"⏳ Запрашиваем день: {current_date} (параметр dateFrom: {date_from_str})")
        
        # flag=1 выгружает ВСЕ заказы, созданные в этот день
        params = {
            "dateFrom": date_from_str,
            "flag": 1
        }
        
        resp = safe_request(url, headers=headers, params=params, timeout=120)
        
        if resp.status_code == 400:
            log.error(f"❌ Ошибка 400: Неверный формат параметров: {resp.text}")
            break
            
        resp.raise_for_status()
        orders = resp.json() # Этот метод возвращает сразу массив JSON
        
        if isinstance(orders, list) and orders:
            all_orders.extend(orders)
            log.info(f"   📊 Подтянуто за день: +{len(orders)} заказов (всего собрано: {len(all_orders)})")
        else:
            log.info(f"   📭 За {current_date} заказов нет")

        # Переходим к следующему дню
        current_date += timedelta(days=1)
        
        # Лимит метода очень жесткий (1 запрос в минуту). 
        # Делаем паузу, чтобы не ловить постоянные 429 ошибки.
        time.sleep(15) 

    return all_orders

def fetch_marketplace_sales_raw():
    """
    Запрашивает продажи и возвраты из API Статистики WB за последние 5 дней.
    Использует формат даты RFC3339 и flag=1.
    """
    if not WB_TOKEN_STAT:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_STATISTICS")

    headers = {"Authorization": WB_TOKEN_STAT}
    all_sales = []
    
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
    
    # Синхронизируем интервал с заказами — берем 5 дней
    start_date = date.today() - timedelta(days=5)
    end_date = date.today()

    log.info(f"🛰️ Запрос ПРОДАЖ из API Статистики WB с {start_date} по {end_date}")

    current_date = start_date
    while current_date <= end_date:
        date_from_str = f"{current_date.isoformat()}T00:00:00"
        log.info(f"⏳ Запрашиваем продажи за день: {current_date}")
        
        params = {
            "dateFrom": date_from_str,
            "flag": 1
        }
        
        resp = safe_request(url, headers=headers, params=params, timeout=120)
        if resp.status_code == 400:
            log.error(f"❌ Ошибка 400 (Продажи): {resp.text}")
            break
            
        resp.raise_for_status()
        sales = resp.json()
        
        if isinstance(sales, list) and sales:
            all_sales.extend(sales)
            log.info(f"   📊 Подтянуто продаж: +{len(sales)} (всего собрано: {len(all_sales)})")
        else:
            log.info(f"   📭 За {current_date} продаж/возвратов нет")

        current_date += timedelta(days=1)
        time.sleep(15)  # Соблюдаем лимит 1 запр/мин

    return all_sales
# Для этой функции нужен токен КОНТЕНТА
WB_TOKEN_CONTENT = os.getenv("WB_TOKEN_CONTENT")

def fetch_content_products_raw():
    """
    Выгружает все карточки товаров селлера из API Контента WB.
    Использует правильную курсорную пагинацию со значением sort.ascending: True.
    """
    if not WB_TOKEN_CONTENT:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_CONTENT")

    headers = {
        "Authorization": WB_TOKEN_CONTENT,
        "Content-Type": "application/json"
    }
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    
    all_cards = []
    cursor_updated_at = None
    cursor_nm_id = None
    
    log.info("🛰️ Начало выгрузки карточек товаров из API Контента WB...")
    
    while True:
        # Базовый payload согласно правилам пагинации 2026 года
        payload = {
            "settings": {
                "sort": {
                    "ascending": True  # Обязательно для инкремента и корректного курсора
                },
                "cursor": {
                    "limit": 100
                },
                "filter": {
                    "withPhoto": -1
                }
            }
        }
        
        # Если это вторая и далее страницы — передаем сохраненный курсор внутрь объекта cursor
        if cursor_updated_at and cursor_nm_id:
            payload["settings"]["cursor"]["updatedAt"] = cursor_updated_at
            payload["settings"]["cursor"]["nmID"] = cursor_nm_id

        # Делаем POST-запрос через requests (используем таймаут 30 сек)
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        cards = data.get("cards", [])
        if not cards:
            break
            
        all_cards.extend(cards)
        log.info(f"   📥 Скачано карточек: {len(all_cards)}")
        
        # Вытаскиваем параметры курсора для следующего шага
        cursor_data = data.get("cursor", {})
        cursor_updated_at = cursor_data.get("updatedAt")
        cursor_nm_id = cursor_data.get("nmID")
        
        # Если лимит total в ответе меньше limit запроса (100) или пропал курсор — выгрузка завершена
        if len(cards) < 100 or not cursor_updated_at:
            break
            
        time.sleep(0.6) # Пауза 600 мс по спецификации лимитов WB Контента

    return all_cards
# Токен аналитики из окружения
WB_TOKEN_ANALYTICS = os.getenv("WB_TOKEN_ANALYTICS")

def fetch_analytics_wb_stocks_raw(all_nm_ids, all_chrt_ids):
    """POST /api/analytics/v1/stocks-report/wb-warehouses (Текущие остатки FBO)"""
    if not WB_TOKEN_ANALYTICS:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_ANALYTICS")

    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
    
    payload = {
        "nmIds": all_nm_ids[:1000],
        "chrtIds": all_chrt_ids[:1000],
        "limit": 250000,
        "offset": 0
    }
    
    log.info("🛰️ Запрос остатков FBO (склады WB) через v1...")
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json().get("data", {}).get("items", [])


def fetch_analytics_seller_stocks_raw(all_nm_ids, all_chrt_ids):
    """
    2. Остатки на складах продавца (FBS) - Текущие штуки
    POST /api/analytics/v1/stocks-report/seller-warehouses
    """
    if not WB_TOKEN_ANALYTICS:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_ANALYTICS")

    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/seller-warehouses"
    
    payload = {
        "nmIds": all_nm_ids[:1000],
        "chrtIds": all_chrt_ids[:1000],
        "limit": 250000,
        "offset": 0
    }
    
    log.info("🛰️ Запрос оперативных остатков FBS (склады продавца) через v1...")
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    
    if resp.status_code == 204 or not resp.text.strip():
        log.warning("⚠️ На домашних складах FBS сейчас нет остатков (0 шт). Пропускаем.")
        return []
        
    resp.raise_for_status()
    try:
        return resp.json().get("data", {}).get("items", [])
    except Exception as e:
        log.error(f"❌ Ошибка декодирования JSON от FBS-складов: {e}")
        return []


def fetch_analytics_products_business_raw(all_nm_ids):
    """
    3. Бизнес-аналитика остатков (Оборачиваемость, дефициты)
    POST /api/v2/stocks-report/products/products
    """
    if not WB_TOKEN_ANALYTICS:
        raise ValueError("❌ Ошибка: В .env файле отсутствует WB_TOKEN_ANALYTICS")

    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/v2/stocks-report/products/groups"
    
    payload = {
        "nmIDs": all_nm_ids[:1000],
        "currentPeriod": {
            # Используем импортированные напрямую классы date и timedelta
            "start": (date.today() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "end": time.strftime("%Y-%m-%d")
        },
        "stockType": "",  
        "skipDeletedNm": True,
        "availabilityFilters": ["deficient", "actual", "balanced", "nonActual", "nonLiquid", "invalidData"],
        "orderBy": {"field": "avgOrders", "mode": "asc"},
        "limit": 1000,
        "offset": 0
    }
    
    log.info("🛰️ Запрос глубоких трендов остатков (оборачиваемость) через v2...")
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    
    try:
        return resp.json().get("data", {}).get("items", [])
    except Exception as e:
        log.error(f"❌ Ошибка декодирования JSON бизнес-аналитики: {e}")
        return []
