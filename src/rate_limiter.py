"""
Адаптивный rate limiter (token bucket)
"""
import time
from typing import Optional


class AdaptiveRateLimiter:
    def __init__(self, initial_delay: float = 0.35, min_delay: float = 0.1, max_delay: float = 5.0):
        self.delay = initial_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time: Optional[float] = None
        self.error_count = 0
        self.success_count = 0

    async def wait(self):
        """Ждёт перед следующим запросом"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            wait_time = max(0, self.delay - elapsed)
            if wait_time > 0:
                import asyncio
                await asyncio.sleep(wait_time)

        self.last_request_time = time.time()

    def on_success(self):
        """Вызывается после успешного запроса"""
        self.success_count += 1
        self.error_count = 0

        # После 10 успешных запросов подряд — уменьшаем задержку
        if self.success_count >= 10:
            self.delay = max(self.min_delay, self.delay * 0.9)
            self.success_count = 0

    def on_error(self):
        """Вызывается после ошибки (FloodWait, timeout и т.п.)"""
        self.error_count += 1
        self.success_count = 0

        # После ошибки — увеличиваем задержку
        self.delay = min(self.max_delay, self.delay * 1.5)

    def on_flood_wait(self, seconds: int):
        """Вызывается при FloodWait"""
        # Резко увеличиваем задержку после FloodWait
        self.delay = min(self.max_delay, max(self.delay * 2, seconds / 10))
        self.error_count += 1
        self.success_count = 0

    def get_current_delay(self) -> float:
        """Возвращает текущую задержку"""
        return self.delay
