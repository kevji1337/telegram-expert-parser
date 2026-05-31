"""
Рекурсивный поиск и расширение очереди
"""
from typing import Set, List, Tuple


class RecursiveSearchQueue:
    """Очередь для рекурсивного поиска по упоминаниям"""
    
    def __init__(self, max_depth: int = 2, max_channels: int = 500):
        self.max_depth = max_depth
        self.max_channels = max_channels
        self.seen_usernames: Set[str] = set()
        self.queue: List[Tuple[str, int, str]] = []  # (username, depth, source)
        self.cross_promo_network: dict[str, Set[str]] = {}  # username -> set of mentioned usernames
        
    def add_initial_channels(self, usernames: List[str]):
        """Добавляет начальные каналы (из поиска по ключам)"""
        for username in usernames:
            if username not in self.seen_usernames:
                self.queue.append((username, 0, "keyword_search"))
                self.seen_usernames.add(username)
    
    def add_mentions(self, source_username: str, mentioned_usernames: List[str], current_depth: int):
        """Добавляет упоминания из канала в очередь"""
        if current_depth >= self.max_depth:
            return
        
        if len(self.seen_usernames) >= self.max_channels:
            return
        
        # Сохраняем для кросс-промо анализа
        if source_username not in self.cross_promo_network:
            self.cross_promo_network[source_username] = set()
        
        for username in mentioned_usernames:
            username = username.lower().strip()
            if not username or username in self.seen_usernames:
                continue
            
            self.cross_promo_network[source_username].add(username)
            self.queue.append((username, current_depth + 1, f"mentioned_by_{source_username}"))
            self.seen_usernames.add(username)
            
            if len(self.seen_usernames) >= self.max_channels:
                break
    
    def get_next(self) -> Tuple[str, int, str] | None:
        """Возвращает следующий канал из очереди"""
        if not self.queue:
            return None
        return self.queue.pop(0)
    
    def is_empty(self) -> bool:
        """Проверяет пуста ли очередь"""
        return len(self.queue) == 0
    
    def detect_cross_promo_networks(self, min_mutual_mentions: int = 2) -> List[Set[str]]:
        """
        Детектит кросс-промо сети (каналы упоминают друг друга)
        
        Возвращает список сетей (каждая сеть = set of usernames)
        """
        networks: List[Set[str]] = []
        processed: Set[str] = set()
        
        for username, mentions in self.cross_promo_network.items():
            if username in processed:
                continue
            
            # Ищем взаимные упоминания
            network = {username}
            for mentioned in mentions:
                if mentioned in self.cross_promo_network:
                    # Проверяем взаимность
                    if username in self.cross_promo_network[mentioned]:
                        network.add(mentioned)
            
            if len(network) >= min_mutual_mentions:
                networks.append(network)
                processed.update(network)
        
        return networks
    
    def get_stats(self) -> dict:
        """Возвращает статистику очереди"""
        depth_counts = {}
        for _, depth, _ in self.queue:
            depth_counts[depth] = depth_counts.get(depth, 0) + 1
        
        return {
            "total_seen": len(self.seen_usernames),
            "queue_size": len(self.queue),
            "depth_distribution": depth_counts,
            "cross_promo_networks": len(self.detect_cross_promo_networks())
        }
