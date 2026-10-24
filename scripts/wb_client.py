import os
import time
import random
import uuid
import json
import logging
import base64
from datetime import datetime, timezone, date, timedelta
import requests
from dotenv import load_dotenv

# Настройка логирования в соответствии с промышленным стандартом
logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

# Инициализация путей окружения
ROOT_DIR = r"D:\Documents\Dev\projects\new-bi-project"
dotenv_path = os.path.join(ROOT_DIR, "scripts", ".env")
load_dotenv(dotenv_path=dotenv_path)

# Загрузка токенов из конфигурации
WB_TOKEN_STAT = os.getenv("WB_TOKEN_STATISTICS")
WB_TOKEN_CONTENT = os.getenv("WB_TOKEN_CONTENT")
WB_TOKEN_ANALYTICS = os.getenv("WB_TOKEN_ANALYTICS")

def mask_token(token: str) -> str:
    """Маскирует токен для безопасности логов."""
    if not token or len(token) < 20:
        return "***hidden***"
    return f"{token[:8]}...{token[-8:]}"

def write_json_log(level: str, client_req_id: str, method: str, url: str, status_code: int = None, wb_req_id: str = None, message: str = None, error: str = None, masked_token_str: str = None) -> None:
    """Формирует строго структурированную JSON-строку лога."""
    log_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "client_request_id": client_req_id,
        "method": method,
        "url": url,
        "token": masked_token_str
    }
    if status_code is not None: log_payload["status_code"] = status_code
    if wb_req_id: log_payload["wb_request_id"] = wb_req_id
    if message: log_payload["message"] = message
    if error: log_payload["error"] = error
    
    print(json.dumps(log_payload), flush=True)

def inspect_wb_token(token: str, token_name: str) -> bool:
    """Pre-flight проверка TTL токена."""
    if not token:
        write_json_log("ERROR", "pre-flight", "NONE", "NONE", message=f"Токен {token_name} отсутствует в конфигурации")
        return False
    try:
        parts = token.split('.')
        if len(parts) != 3:
            write_json_log("ERROR", "pre-flight", "NONE", "NONE", message=f"Неверный формат JWT {token_name}")
            return False
            
        payload_b64 = parts[1]
        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += '=' * (4 - rem)
            
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload_data = json.loads(payload_bytes.decode('utf-8'))
        
        exp_timestamp = payload_data.get("exp")
        if not exp_timestamp:
            write_json_log("WARNING", "pre-flight", "NONE", "NONE", message=f"В токене {token_name} отсутствует поле exp")
            return True
            
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        days_left = (exp_datetime - datetime.now(timezone.utc)).days
        
        if days_left <= 0:
            write_json_log("CRITICAL", "pre-flight", "NONE", "NONE", message=f"Срок действия токена {token_name} ИСТЕК")
            return False
        elif days_left <= 5:
            write_json_log("ALERT", "pre-flight", "NONE", "NONE", message=f"Токен {token_name} в зоне 120-часового карантина. Осталось дней: {days_left}")
        else:
            write_json_log("INFO", "pre-flight", "NONE", "NONE", message=f"Токен {token_name} валиден. Оставшийся TTL: {days_left} дней.")
            
        return True
    except Exception as e:
        write_json_log("ERROR", "pre-flight", "NONE", "NONE", error=str(e), message=f"Ошибка валидации токена {token_name}")
        return False

def safe_request(method: str, url: str, headers: dict = None, params: dict = None, json_data: dict = None, timeout: int = 60, max_retries: int = 4) -> requests.Response:
    """Отказоустойчивый HTTP-транспорт с адаптивным ретраем (429), обработкой 409 кодов и джиттером."""
    headers = headers.copy() if headers else {}
    client_req_id = str(uuid.uuid4())
    headers["client_request_id"] = client_req_id
    
    masked_auth = mask_token(headers.get("Authorization", ""))
    base_wait_409 = 5.0
    
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method=method.upper(), url=url, headers=headers, params=params, json=json_data, timeout=timeout)
            wb_req_id = resp.headers.get("x-request-id", "unknown_wb_id")
            
            if resp.status_code not in (429, 409):
                write_json_log("INFO", client_req_id, method, url, status_code=resp.status_code, wb_req_id=wb_req_id, masked_token_str=masked_auth)
                return resp
                
            if resp.status_code == 429:
                retry_after = resp.headers.get('X-Ratelimit-Retry')
                wait_time = float(retry_after) if retry_after else 60.0
                jitter = wait_time * random.uniform(-0.25, 0.25)
                final_wait = max(0.5, wait_time + jitter)
                
                write_json_log("WARNING", client_req_id, method, url, status_code=429, wb_req_id=wb_req_id, masked_token_str=masked_auth,
                               message=f"API Rate Limit 429. Ожидание {final_wait:.2f} сек.")
                if attempt < max_retries:
                    time.sleep(final_wait)
                    continue
                break
                
            if resp.status_code == 409:
                wait_time = base_wait_409 * (2 ** (attempt - 1))
                jitter = wait_time * random.uniform(-0.25, 0.25)
                final_wait = max(1.0, wait_time + jitter)
                
                write_json_log("WARNING", client_req_id, method, url, status_code=409, wb_req_id=wb_req_id, masked_token_str=masked_auth,
                               message=f"Conflict 409. Ожидание {final_wait:.2f} сек.")
                if attempt < max_retries:
                    time.sleep(final_wait)
                    continue
                break
                
        except requests.exceptions.RequestException as e:
            wait_time = 5.0 * attempt
            write_json_log("ERROR", client_req_id, method, url, masked_token_str=masked_auth, error=str(e),
                           message=f"Сетевая ошибка. Повтор через {wait_time} сек.")
            if attempt < max_retries:
                time.sleep(wait_time)
                continue
            raise Exception(f"Запрос провален после {max_retries} попыток сетевых ошибок.")
            
    raise Exception(f"Превышено число попыток ретрая ({max_retries}). Статус ответа сервера: {resp.status_code}")

def fetch_marketplace_orders_raw() -> list:
    """1. Выгружает сырые заказы из API Статистики WB за последние 5 дней (flag=1)."""
    if not inspect_wb_token(WB_TOKEN_STAT, "WB_TOKEN_STATISTICS"):
        raise ValueError("Префлай-валидация токена статистики провалена.")
        
    headers = {"Authorization": WB_TOKEN_STAT}
    all_orders = []
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
    
    start_date = date.today() - timedelta(days=5)
    end_date = date.today()
    
    current_date = start_date
    while current_date <= end_date:
        date_from_str = f"{current_date.isoformat()}T00:00:00"
        params = {"dateFrom": date_from_str, "flag": 1}
        
        resp = safe_request("GET", url, headers=headers, params=params, timeout=120)
        if resp.status_code == 400:
            write_json_log("ERROR", "pipeline_orders", "GET", url, status_code=400, message=f"Ошибка параметров 400: {resp.text}")
            break
            
        orders = resp.json()
        if isinstance(orders, list) and orders:
            all_orders.extend(orders)
            
        current_date += timedelta(days=1)
        time.sleep(1.0)
        
    return all_orders

def fetch_marketplace_sales_raw() -> list:
    """2. Выгружает продажи и возвраты из API Статистики WB за последние 5 дней (flag=1)."""
    if not inspect_wb_token(WB_TOKEN_STAT, "WB_TOKEN_STATISTICS"):
        raise ValueError("Префлай-валидация токена статистики провалена.")
        
    headers = {"Authorization": WB_TOKEN_STAT}
    all_sales = []
    url = "https://statistics-api.wildberries.ru/api/v1/supplier/sales"
    
    start_date = date.today() - timedelta(days=5)
    end_date = date.today()
    
    current_date = start_date
    while current_date <= end_date:
        date_from_str = f"{current_date.isoformat()}T00:00:00"
        params = {"dateFrom": date_from_str, "flag": 1}
        
        resp = safe_request("GET", url, headers=headers, params=params, timeout=120)
        if resp.status_code == 400:
            write_json_log("ERROR", "pipeline_sales", "GET", url, status_code=400, message=f"Ошибка параметров 400: {resp.text}")
            break
            
        sales = resp.json()
        if isinstance(sales, list) and sales:
            all_sales.extend(sales)
            
        current_date += timedelta(days=1)
        time.sleep(1.0)
        
    return all_sales

def fetch_content_products_raw() -> list:
    """3. Выгружает все карточки товаров селлера из API Контента с честной курсорной пагинацией."""
    if not inspect_wb_token(WB_TOKEN_CONTENT, "WB_TOKEN_CONTENT"):
        raise ValueError("Префлай-валидация токена контента провалена.")
        
    headers = {"Authorization": WB_TOKEN_CONTENT, "Content-Type": "application/json"}
    url = "https://content-api.wildberries.ru/content/v2/get/cards/list"
    
    all_cards = []
    cursor_updated_at = None
    cursor_nm_id = None
    
    while True:
        payload = {
            "settings": {
                "sort": {"ascending": True},
                "cursor": {"limit": 100},
                "filter": {"withPhoto": -1}
            }
        }
        if cursor_updated_at and cursor_nm_id:
            payload["settings"]["cursor"]["updatedAt"] = cursor_updated_at
            payload["settings"]["cursor"]["nmID"] = cursor_nm_id
            
        resp = safe_request("POST", url, headers=headers, json_data=payload, timeout=30)
        data = resp.json()
        
        cards = data.get("cards", [])
        if not cards:
            break
            
        all_cards.extend(cards)
        
        cursor_data = data.get("cursor", {})
        cursor_updated_at = cursor_data.get("updatedAt")
        cursor_nm_id = cursor_data.get("nmID")
        
        if len(cards) < 100 or not cursor_updated_at:
            break
            
        time.sleep(0.6)
        
    return all_cards

def fetch_analytics_wb_stocks_raw(all_nm_ids: list, all_chrt_ids: list) -> list:
    """4. Выгружает текущие остатки FBO (склады Wildberries) из API Аналитики (ограничение до 1000 позиций)."""
    if not inspect_wb_token(WB_TOKEN_ANALYTICS, "WB_TOKEN_ANALYTICS"):
        raise ValueError("Префлай-валидация токена аналитики провалена.")
        
    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
    
    payload = {
        "nmIds": all_nm_ids[:1000],
        "chrtIds": all_chrt_ids[:1000],
        "limit": 250000,
        "offset": 0
    }
    
    resp = safe_request("POST", url, headers=headers, json_data=payload, timeout=60)
    return resp.json().get("data", {}).get("items", [])

def fetch_analytics_seller_stocks_raw(all_nm_ids: list, all_chrt_ids: list) -> list:
    """5. Выгружает остатки на домашних складах продавца (FBS) из API Аналитики (с обработкой пустых ответов 204)."""
    if not inspect_wb_token(WB_TOKEN_ANALYTICS, "WB_TOKEN_ANALYTICS"):
        raise ValueError("Префлай-валидация токена аналитики провалена.")
        
    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/seller-warehouses"
    
    payload = {
        "nmIds": all_nm_ids[:1000],
        "chrtIds": all_chrt_ids[:1000],
        "limit": 250000,
        "offset": 0
    }
    
    resp = safe_request("POST", url, headers=headers, json_data=payload, timeout=60)
    if resp.status_code == 204 or not resp.text.strip():
        write_json_log("WARNING", "pipeline_stocks", "POST", url, status_code=resp.status_code, message="На складах продавца FBS нет доступных остатков. Возвращаем пустой список.")
        return []
        
    try:
        return resp.json().get("data", {}).get("items", [])
    except Exception as e:
        write_json_log("ERROR", "pipeline_stocks", "POST", url, error=str(e), message="Ошибка декодирования JSON FBS-остатков")
        return []

def fetch_analytics_products_business_raw(all_nm_ids: list) -> list:
    """6. Выгружает глубокую бизнес-аналитику (оборачиваемость, дефициты) из API Аналитики v2."""
    if not inspect_wb_token(WB_TOKEN_ANALYTICS, "WB_TOKEN_ANALYTICS"):
        raise ValueError("Префлай-валидация токена аналитики провалена.")
        
    headers = {"Authorization": WB_TOKEN_ANALYTICS, "Content-Type": "application/json"}
    url = "https://seller-analytics-api.wildberries.ru/api/v2/stocks-report/products/groups"
    
    start_str = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    end_str = date.today().strftime("%Y-%m-%d")
    
    payload = {
        "nmIDs": all_nm_ids[:1000],
        "currentPeriod": {"start": start_str, "end": end_str},
        "stockType": "",  
        "skipDeletedNm": True,
        "availabilityFilters": ["deficient", "actual", "balanced", "nonActual", "nonLiquid", "invalidData"],
        "orderBy": {"field": "avgOrders", "mode": "asc"},
        "limit": 1000,
        "offset": 0
    }
    
    resp = safe_request("POST", url, headers=headers, json_data=payload, timeout=60)
    try:
        return resp.json().get("data", {}).get("items", [])
    except Exception as e:
        write_json_log("ERROR", "pipeline_business", "POST", url, error=str(e), message="Ошибка декодирования JSON бизнес-аналитики")
        return []