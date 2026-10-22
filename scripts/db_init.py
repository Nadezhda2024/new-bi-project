import os
import psycopg2
from dotenv import load_dotenv

# Корректно находим .env в папке scripts/
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, 'scripts', '.env'))

def init_db():
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    
    # Теперь путь ведет в правильную архитектурную папку sql/staging/
        # Прописываем точное имя файла с префиксом 06 из нашей новой структуры
    sql_file_path = os.path.join(BASE_DIR, 'sql', 'staging', '06_create_staging_raw_financial_reports.sql')

    
    if not os.path.exists(sql_file_path):
        print(f"Ошибка: SQL-файл не найден по пути {sql_file_path}")
        return

    try:
        conn = psycopg2.connect(
            dbname=dbname, user=user, password=password, host=host, port=port
        )
        cursor = conn.cursor()
        
        print("Подключение к PostgreSQL успешно. Создаем схему staging...")
        cursor.execute("CREATE SCHEMA IF NOT EXISTS staging;")
        
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
        cursor.execute(sql_script)
        conn.commit()
        print("Структура staging.raw_financial_reports успешно инициализирована.")
        
    except Exception as e:
        print(f"Критическая ошибка при инициализации базы данных: {e}")
        if 'conn' in locals():
            conn.rollback()
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    init_db()
