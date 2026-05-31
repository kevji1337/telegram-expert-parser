"""
SQLite кэш для каналов и поиска (замена JSON)
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Any, Optional


class SQLiteCache:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Создаёт таблицы если их нет"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Таблица для кэша поиска
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                keyword TEXT PRIMARY KEY,
                channel_ids TEXT,
                created_at REAL
            )
        """)

        # Таблица для кэша каналов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_cache (
                channel_id TEXT PRIMARY KEY,
                data TEXT,
                created_at REAL
            )
        """)

        conn.commit()
        conn.close()

    def get_search(self, keyword: str, ttl_days: int = 3) -> Optional[list[int]]:
        """Получает результаты поиска из кэша"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT channel_ids, created_at FROM search_cache WHERE keyword = ?",
            (keyword,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        channel_ids_json, created_at = row
        age_days = (datetime.now().timestamp() - created_at) / 86400

        if age_days > ttl_days:
            return None

        return json.loads(channel_ids_json)

    def set_search(self, keyword: str, channel_ids: list[int]):
        """Сохраняет результаты поиска в кэш"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO search_cache (keyword, channel_ids, created_at) VALUES (?, ?, ?)",
            (keyword, json.dumps(channel_ids), datetime.now().timestamp())
        )

        conn.commit()
        conn.close()

    def get_channel(self, channel_id: str, ttl_days: int = 7) -> Optional[dict]:
        """Получает данные канала из кэша"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT data, created_at FROM channel_cache WHERE channel_id = ?",
            (channel_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        data_json, created_at = row
        age_days = (datetime.now().timestamp() - created_at) / 86400

        if age_days > ttl_days:
            return None

        return json.loads(data_json)

    def set_channel(self, channel_id: str, data: dict):
        """Сохраняет данные канала в кэш"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT OR REPLACE INTO channel_cache (channel_id, data, created_at) VALUES (?, ?, ?)",
            (channel_id, json.dumps(data), datetime.now().timestamp())
        )

        conn.commit()
        conn.close()

    def get_all_search(self) -> dict[str, list[int]]:
        """Получает весь кэш поиска (для совместимости)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT keyword, channel_ids FROM search_cache")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for keyword, channel_ids_json in rows:
            result[keyword] = json.loads(channel_ids_json)

        return result

    def get_all_channels(self) -> dict[str, dict]:
        """Получает весь кэш каналов (для совместимости)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT channel_id, data FROM channel_cache")
        rows = cursor.fetchall()
        conn.close()

        result = {}
        for channel_id, data_json in rows:
            result[channel_id] = json.loads(data_json)

        return result
