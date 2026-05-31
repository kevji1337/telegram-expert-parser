"""
Аналитика каналов
"""
import re
from typing import List


def calc_growth_rate(current_subs: int, cached_subs: int, days_diff: int) -> float:
    """
    Считает темп роста подписчиков

    Возвращает процент роста в день
    """
    if not cached_subs or cached_subs == 0 or days_diff == 0:
        return 0.0

    growth = current_subs - cached_subs
    growth_per_day = growth / days_diff
    growth_rate = (growth_per_day / cached_subs) * 100

    return round(growth_rate, 2)


def calc_growth_rate_from_history(history: list[tuple[float, int]]) -> float:
    """
    Считает темп роста (% в день) по истории замеров.

    history: [(ts_unix, subs), ...] отсортированный по времени.
    Берём первый и последний замер с расстоянием >=1 день, считаем по ним.
    Если в истории <2 точек или интервал <1 день — возвращаем 0.0.
    """
    if not history or len(history) < 2:
        return 0.0

    first_ts, first_subs = history[0]
    last_ts, last_subs = history[-1]

    days_diff = (last_ts - first_ts) / 86400
    if days_diff < 1.0 or first_subs <= 0:
        return 0.0

    growth_per_day = (last_subs - first_subs) / days_diff
    return round((growth_per_day / first_subs) * 100, 2)


def analyze_sentiment(texts: List[str]) -> float:
    """
    Простой sentiment analysis (позитив/негатив)

    Возвращает скор от -1 (негатив) до +1 (позитив)
    """
    if not texts:
        return 0.0
    
    # Позитивные слова
    positive_words = [
        "отлично", "супер", "круто", "спасибо", "благодарю", "помогло", "полезно",
        "рекомендую", "лучший", "топ", "класс", "огонь", "кайф", "восторг",
        "успех", "результат", "достижение", "прогресс", "рост", "победа"
    ]
    
    # Негативные слова
    negative_words = [
        "плохо", "ужасно", "отстой", "не помогло", "бесполезно", "обман", "развод",
        "мошенник", "жалоба", "разочарован", "не рекомендую", "провал", "фейк",
        "скам", "лохотрон", "впустую", "зря", "потерял", "проблема", "ошибка"
    ]
    
    positive_count = 0
    negative_count = 0
    total_words = 0
    
    for text in texts:
        if not text:
            continue
        
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        total_words += len(words)
        
        for word in positive_words:
            positive_count += text_lower.count(word)
        
        for word in negative_words:
            negative_count += text_lower.count(word)
    
    if total_words == 0:
        return 0.0
    
    # Нормализуем на количество слов
    positive_score = positive_count / total_words
    negative_score = negative_count / total_words
    
    # Итоговый скор от -1 до +1
    sentiment = (positive_score - negative_score) * 100
    sentiment = max(-1.0, min(1.0, sentiment))
    
    return round(sentiment, 3)


def detect_topic_clusters(posts: List) -> dict:
    """
    Детектит топ-темы в постах (простой подход через частотный анализ)

    Возвращает топ-5 тем с частотой
    """
    if not posts:
        return {}
    
    # Стоп-слова (исключаем из анализа)
    stop_words = {
        "и", "в", "на", "с", "по", "для", "как", "что", "это", "не", "а", "но",
        "или", "из", "к", "о", "у", "за", "от", "до", "при", "про", "под", "над"
    }
    
    word_freq = {}
    
    for post in posts[:20]:
        if not hasattr(post, 'message') or not post.message:
            continue
        
        text = post.message.lower()
        words = re.findall(r'\b[а-яё]{4,}\b', text)  # только русские слова длиной 4+
        
        for word in words:
            if word in stop_words:
                continue
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Топ-5 слов
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return dict(sorted_words[:5])
