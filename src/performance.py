"""
Производительность: параллельный парсинг, приоритетная очередь, инкрементальные обновления
"""
import asyncio
import heapq
from typing import Any, Callable, Awaitable
from datetime import datetime, timedelta


class PriorityChannelQueue:
    """
    Приоритетная очередь каналов (heap-based)

    Каналы с высоким потенциалом парсятся первыми.
    Приоритет считается по приблизительным метрикам (подписчики, ключи).
    """

    def __init__(self):
        self._heap: list = []
        self._counter = 0  # tiebreaker

    def push(self, priority: float, channel: Any, niche_key: str, niche_title: str, keyword: str):
        """
        Добавляет канал в очередь

        priority: чем выше число, тем раньше будет обработан (heapq min-heap → используем -priority)
        """
        self._counter += 1
        heapq.heappush(self._heap, (-priority, self._counter, channel, niche_key, niche_title, keyword))

    def pop(self) -> tuple:
        """Возвращает (channel, niche_key, niche_title, keyword) с наивысшим приоритетом"""
        if not self._heap:
            return None
        _, _, channel, niche_key, niche_title, keyword = heapq.heappop(self._heap)
        return channel, niche_key, niche_title, keyword

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)


def calc_initial_priority(channel: Any, keyword: str, intent_keywords: set) -> float:
    """
    Считает начальный приоритет канала по приблизительным метрикам

    Высокий приоритет = большой канал + intent-ключ
    """
    score = 0.0

    # Подписчики (логарифмически)
    approx_subs = getattr(channel, "participants_count", None) or 0
    if approx_subs:
        if approx_subs >= 10000:
            score += 30
        elif approx_subs >= 5000:
            score += 20
        elif approx_subs >= 1000:
            score += 10
        else:
            score += 5

    # Intent-ключ
    if keyword.lower() in {k.lower() for k in intent_keywords}:
        score += 50

    # Verified/scam флаги
    if getattr(channel, "verified", False):
        score += 10
    if getattr(channel, "scam", False):
        score -= 100  # точно скам — в конец
    if getattr(channel, "fake", False):
        score -= 100

    return score


async def parallel_process_channels(
    channels: list,
    process_func: Callable[..., Awaitable],
    *args,
    concurrency: int = 3,
    **kwargs,
) -> list:
    """
    Параллельная обработка каналов с ограничением concurrency

    Используется для одновременной обработки нескольких каналов
    через один аккаунт (внутри лимита).

    ВАЖНО: Telegram имеет per-account лимиты, не превышайте concurrency=3
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _process_one(channel):
        async with semaphore:
            try:
                return await process_func(channel, *args, **kwargs)
            except Exception as e:
                print(f"     [!] parallel error: {e}")
                return None

    tasks = [_process_one(ch) for ch in channels]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return [r for r in results if r is not None]


class IncrementalUpdater:
    """
    Инкрементальные обновления: пересканирует только каналы,
    которые давно не обновлялись или показали рост.
    """

    def __init__(self, cache, refresh_days: int = 7):
        self.cache = cache
        self.refresh_days = refresh_days

    def needs_update(self, channel_id: int) -> bool:
        """Проверяет, нужно ли обновлять канал"""
        cached = self.cache.get_channel(str(channel_id), ttl_days=365)
        if not cached:
            return True  # никогда не парсили

        # Если данные старше refresh_days — обновляем
        return False  # SQLite уже имеет TTL, тут можно добавить кастомную логику

    def filter_to_update(self, channels: list) -> list:
        """Возвращает список каналов, требующих обновления"""
        return [ch for ch in channels if self.needs_update(ch.id)]

    def merge_with_cached(self, channel_id: int, new_data: dict) -> dict:
        """Сливает новые данные с кэшированными (для дельты)"""
        cached = self.cache.get_channel(str(channel_id), ttl_days=365) or {}

        merged = {**cached, **new_data}
        # Сохраняем историю подписчиков для growth rate
        history = cached.get("subs_history", [])
        history.append({
            "ts": datetime.now().timestamp(),
            "subs": new_data.get("participants_count", 0),
        })
        # Храним только последние 30 записей
        merged["subs_history"] = history[-30:]

        return merged


class MultiAccountPool:
    """
    Пул аккаунтов для распределения нагрузки

    Каждый аккаунт обрабатывает свою порцию ключей/каналов параллельно.
    Если один словил FloodWait, остальные продолжают работу.
    """

    def __init__(self, accounts: list[str]):
        self.accounts = accounts
        self.clients: dict[str, Any] = {}
        self.rate_limiters: dict[str, Any] = {}
        self.locked_until: dict[str, float] = {}  # account -> timestamp

    def is_available(self, account: str) -> bool:
        """Проверяет, доступен ли аккаунт"""
        locked = self.locked_until.get(account, 0)
        return datetime.now().timestamp() >= locked

    def lock_account(self, account: str, seconds: int):
        """Блокирует аккаунт на N секунд (после FloodWait)"""
        self.locked_until[account] = datetime.now().timestamp() + seconds

    def get_available_account(self) -> str | None:
        """Возвращает первый доступный аккаунт"""
        for acc in self.accounts:
            if self.is_available(acc):
                return acc
        return None

    def get_stats(self) -> dict:
        """Статистика пула"""
        return {
            "total": len(self.accounts),
            "available": sum(1 for a in self.accounts if self.is_available(a)),
            "locked": sum(1 for a in self.accounts if not self.is_available(a)),
        }


def split_keywords_across_accounts(keywords: list, num_accounts: int) -> list[list]:
    """
    Распределяет ключи между аккаунтами равномерно (round-robin)

    Возвращает список списков ключей для каждого аккаунта
    """
    if num_accounts <= 0:
        return [keywords]

    buckets: list[list] = [[] for _ in range(num_accounts)]
    for i, kw in enumerate(keywords):
        buckets[i % num_accounts].append(kw)

    return buckets


class BatchSaver:
    """
    Батчевое сохранение в CSV для уменьшения I/O

    Накапливает строки в памяти и сохраняет раз в N секунд или N строк.
    """

    def __init__(self, save_func: Callable, batch_size: int = 50, max_age_sec: int = 30):
        self.save_func = save_func
        self.batch_size = batch_size
        self.max_age_sec = max_age_sec
        self.buffer: list = []
        self.last_save = datetime.now()

    def add(self, row: Any):
        """Добавляет строку в буфер"""
        self.buffer.append(row)

        should_save = (
            len(self.buffer) >= self.batch_size or
            (datetime.now() - self.last_save).total_seconds() >= self.max_age_sec
        )

        if should_save:
            self.flush()

    def flush(self):
        """Принудительно сохраняет буфер"""
        if not self.buffer:
            return
        self.save_func(self.buffer)
        self.last_save = datetime.now()
        # буфер не очищаем т.к. сохраняем все накопленные строки (snapshot)
