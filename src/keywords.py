"""
Маркеры и классификация ключевых слов
"""
import re

# Маркеры для классификации каналов
EXPERT_MARKERS = [
    "меня зовут", "автор канал", "автор канала", "мой опыт",
    "помогаю", "консультац", "наставничеств", "коуч", "ментор",
    "психолог", "нутрициолог", "отзыв", "кейсы", "созвон", "разбор", "запись",
]

NEWS_MARKERS = ["новости", "редакция", "сми", "издание", "пресс-служб", "хроника"]
MEDIA_MARKERS = ["медиа", "журнал", "газета", "издательств"]
BRAND_MARKERS = ["официальный канал", "наша компания", "интернет-магазин", "маркетплейс", "доставка"]
AGGREGATOR_MARKERS = ["подборк", "топ-", "сборник", "лучшее за", "агрегатор"]
COMMUNITY_MARKERS = ["сообщество", "наш чат", "обсуждаем", "комьюнити"]

BLACKLIST_MARKERS: list[tuple[str, str]] = [
    ("магазин", "shop"), ("купить", "shop"), ("промокод", "shop"),
    ("официальн", "brand"), ("ваканси", "brand"),
    ("подборк", "aggregator"), ("агрегатор", "aggregator"),
    ("новости", "news"), ("редакция", "news"),
    ("казино", "brand"), ("ставки", "brand"),
]

# Слабые ключевые слова (дают много шума)
WEAK_KEYWORDS = {
    "абьюз", "тревога", "анализы", "работа", "вакансии", "кардио",
    "ии", "ai", "python", "javascript", "бизнес", "стартап"
}

# Intent-ключи (сильно сигналят про экспертность/оффер)
INTENT_KEYWORDS = {
    # AI
    "обучение нейросетям", "курсы по ии", "курсы по нейросетям", "мастер-класс по ии",
    "вебинар по нейросетям", "марафон по ии", "ии наставник", "ии эксперт", "ии консультант",
    "консультация по ии", "внедрение ии", "автоматизация с ии", "обучение chatgpt",
    "обучение midjourney", "промптинг обучение", "prompt engineering курс",
    # IT
    "курсы программирования", "обучение программированию", "it курсы", "курсы разработки",
    "менторство программирование", "наставник программист", "консультация программист",
    "обучение python", "обучение javascript", "обучение веб-разработке",
    "курсы frontend", "курсы backend", "курсы fullstack", "обучение devops",
    "карьера в it", "как стать программистом", "переход в it", "подготовка к собеседованиям",
    # Бизнес
    "бизнес консультант", "бизнес наставник", "бизнес коуч", "консалтинг",
    "консультация по бизнесу", "помощь предпринимателям", "менторство бизнес",
    "курсы для предпринимателей", "обучение бизнесу", "школа предпринимательства",
    "запуск бизнеса обучение", "масштабирование бизнеса", "управление бизнесом курсы",
    "продажи обучение", "переговоры обучение", "инфобизнес обучение",
    "личный бренд обучение", "монетизация экспертности", "упаковка эксперта",
}

# Сильные ключевые слова
STRONG_KEYWORDS = {
    # Общие
    "наставничество", "коуч", "ментор", "консультац", "курс", "обучение",
    # AI
    "chatgpt", "midjourney", "prompt engineering", "ai tools", "нейросети для бизнеса",
    "автоматизация с ии", "ии для предпринимателей",
    # IT
    "программирование", "разработка", "курсы программирования", "it курсы",
    "менторство программирование", "карьера в it",
    # Бизнес
    "бизнес консультант", "бизнес наставник", "бизнес коуч", "консалтинг",
    "предпринимательство", "масштабирование", "инфобизнес", "личный бренд",
}

# Маркеры интента (оффер/продажа)
INTENT_MARKERS = [
    "консультац", "запись", "созвон", "разбор", "наставничеств",
    "курс", "обучение", "интенсив", "вебинар", "марафон",
    "стоимость", "цена", "места", "старт", "поток", "анкета",
    "тариф", "пакет", "программа обучения", "набор",
]

# Регулярки
URL_RE = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
AT_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_]{3,})")

# Маркеры "1-го лица" (личный голос автора)
FIRST_PERSON_MARKERS = [
    r"\bя\b", r"\bмой\b", r"\bмоя\b", r"\bмоё\b", r"\bмне\b", r"\bменя\b",
    r"\bмною\b", r"\bпомогаю\b", r"\bделюсь\b", r"\bрасскажу\b", r"\bпокажу\b",
    r"\bнаучу\b", r"\bпредлагаю\b", r"\bрекомендую\b", r"\bсоветую\b"
]

# Продажные CTA (призывы к действию)
CTA_MARKERS = [
    "запись открыта", "осталось мест", "последние места", "успей записаться",
    "стоимость", "цена", "тариф", "пакет услуг", "оплата", "купить",
    "записаться", "оставить заявку", "заполнить анкету", "забронировать",
    "ограниченное предложение", "скидка", "акция", "бонус при оплате",
    "старт потока", "набор открыт", "регистрация", "участие платное"
]

# Маркеры автопостинга (боты/агрегаторы)
AUTOPOST_MARKERS = [
    "автоматическая публикация", "бот", "парсер", "агрегатор новостей",
    "автопостинг", "rss", "подписывайтесь на канал", "реклама в боте"
]


def classify_keyword_quality(matched_keywords: str) -> str:
    """Классифицирует качество ключевых слов: strong/medium/weak"""
    kws = [k.strip() for k in matched_keywords.split(",") if k.strip()]
    if not kws:
        return "weak"
    normed = [k.lower() for k in kws]
    strong_norm = {s.lower() for s in STRONG_KEYWORDS}
    weak_norm = {s.lower() for s in WEAK_KEYWORDS}
    intent_norm = {s.lower() for s in INTENT_KEYWORDS}

    if any(k in intent_norm for k in normed):
        return "strong"
    if any(k in strong_norm for k in normed):
        return "strong"
    if any(k not in weak_norm for k in normed):
        return "medium"
    return "weak"


def count_intent_keywords(matched_keywords: str) -> int:
    """Считает количество intent-ключей"""
    kws = [k.strip().lower() for k in matched_keywords.split(",") if k.strip()]
    intent_norm = {s.lower() for s in INTENT_KEYWORDS}
    return sum(1 for k in kws if k in intent_norm)


def extract_links(text: str) -> list[str]:
    """Извлекает ссылки из текста"""
    return URL_RE.findall(text or "")


def analyze_external_links(links: list[str]) -> dict[str, bool]:
    """
    Анализирует внешние ссылки и определяет платформы

    Возвращает:
        {
            "has_youtube": bool,
            "has_instagram": bool,
            "has_getcourse": bool,
            "has_taplink": bool,
            "has_calendly": bool,
            "has_forms": bool,
            "has_payment": bool,
            "has_booking": bool,
        }
    """
    result = {
        "has_youtube": False,
        "has_instagram": False,
        "has_getcourse": False,
        "has_taplink": False,
        "has_calendly": False,
        "has_forms": False,
        "has_payment": False,
        "has_booking": False,
    }

    if not links:
        return result

    links_lower = [link.lower() for link in links]

    # YouTube
    if any("youtube.com" in link or "youtu.be" in link for link in links_lower):
        result["has_youtube"] = True

    # Instagram
    if any("instagram.com" in link or "instagr.am" in link for link in links_lower):
        result["has_instagram"] = True

    # GetCourse (платформа онлайн-курсов)
    if any("getcourse" in link or "getkurs" in link for link in links_lower):
        result["has_getcourse"] = True

    # Taplink (лендинги)
    if any("taplink" in link or "tap.link" in link for link in links_lower):
        result["has_taplink"] = True

    # Calendly (бронирование)
    if any("calendly.com" in link for link in links_lower):
        result["has_calendly"] = True
        result["has_booking"] = True

    # Формы (Google Forms, Typeform, Tally)
    if any(
        "forms.gle" in link or "docs.google.com/forms" in link or
        "typeform.com" in link or "tally.so" in link or "forms.yandex" in link
        for link in links_lower
    ):
        result["has_forms"] = True

    # Платёжные системы
    if any(
        "stripe.com" in link or "paypal.com" in link or "boosty.to" in link or
        "patreon.com" in link or "donatepay" in link or "donationalerts" in link
        for link in links_lower
    ):
        result["has_payment"] = True

    # Другие платформы бронирования
    if any(
        "cal.com" in link or "savvycal.com" in link or "acuityscheduling.com" in link or
        "yclients.com" in link or "timely.com" in link
        for link in links_lower
    ):
        result["has_booking"] = True

    return result


def extract_mentions(text: str) -> list[str]:
    """
    Извлекает упоминания каналов из текста (@username и t.me/username)

    Возвращает список уникальных username (без @)
    """
    mentions = set()

    # @username
    for match in AT_RE.finditer(text or ""):
        mentions.add(match.group(1).lower())

    # t.me/username
    tme_pattern = re.compile(r"t\.me/([A-Za-z][A-Za-z0-9_]{3,})", re.IGNORECASE)
    for match in tme_pattern.finditer(text or ""):
        username = match.group(1).lower()
        # Исключаем служебные ссылки
        if username not in ("joinchat", "addstickers", "share", "login", "proxy", "socks"):
            mentions.add(username)

    return sorted(list(mentions))


def analyze_first_person_voice(text: str) -> dict:
    """
    Анализирует использование "1-го лица" в тексте

    Возвращает:
        {
            "first_person_count": int,
            "first_person_density": float (0-1),
            "has_strong_voice": bool
        }
    """
    if not text:
        return {"first_person_count": 0, "first_person_density": 0.0, "has_strong_voice": False}

    text_lower = text.lower()
    words = text_lower.split()
    word_count = len(words)

    if word_count == 0:
        return {"first_person_count": 0, "first_person_density": 0.0, "has_strong_voice": False}

    count = 0
    for pattern in FIRST_PERSON_MARKERS:
        count += len(re.findall(pattern, text_lower))

    density = count / word_count if word_count > 0 else 0
    has_strong_voice = count >= 5 and density >= 0.01  # минимум 5 упоминаний и 1% плотность

    return {
        "first_person_count": count,
        "first_person_density": density,
        "has_strong_voice": has_strong_voice
    }


def analyze_cta_markers(text: str) -> dict:
    """
    Анализирует наличие продажных CTA в тексте

    Возвращает:
        {
            "cta_count": int,
            "has_strong_cta": bool,
            "cta_types": list[str]
        }
    """
    if not text:
        return {"cta_count": 0, "has_strong_cta": False, "cta_types": []}

    text_lower = text.lower()
    count = 0
    found_types = []

    for marker in CTA_MARKERS:
        if marker in text_lower:
            count += 1
            found_types.append(marker)

    has_strong_cta = count >= 3  # минимум 3 разных CTA

    return {
        "cta_count": count,
        "has_strong_cta": has_strong_cta,
        "cta_types": found_types[:5]  # топ-5
    }


def analyze_post_structure(posts: list) -> dict:
    """
    Анализирует структуру постов (регулярные рубрики, серии)

    Возвращает:
        {
            "has_series": bool,
            "has_rubrics": bool,
            "avg_post_length": int,
            "has_consistent_format": bool
        }
    """
    if not posts:
        return {"has_series": False, "has_rubrics": False, "avg_post_length": 0, "has_consistent_format": False}

    # Ищем маркеры серий/рубрик
    series_markers = [r"#\d+", r"часть \d+", r"выпуск \d+", r"день \d+", r"урок \d+"]
    rubric_markers = ["#", "рубрика", "серия", "цикл"]

    series_count = 0
    rubric_count = 0
    lengths = []

    for post in posts[:20]:
        if not hasattr(post, 'message') or not post.message:
            continue

        text = post.message.lower()
        lengths.append(len(post.message))

        for pattern in series_markers:
            if re.search(pattern, text):
                series_count += 1
                break

        for marker in rubric_markers:
            if marker in text:
                rubric_count += 1
                break

    avg_length = sum(lengths) / len(lengths) if lengths else 0

    # Проверка консистентности формата (похожая длина постов)
    if len(lengths) >= 5:
        std_dev = (sum((x - avg_length) ** 2 for x in lengths) / len(lengths)) ** 0.5
        has_consistent = std_dev < avg_length * 0.5  # отклонение < 50%
    else:
        has_consistent = False

    return {
        "has_series": series_count >= 3,
        "has_rubrics": rubric_count >= 3,
        "avg_post_length": int(avg_length),
        "has_consistent_format": has_consistent
    }


def detect_autoposting(posts: list) -> dict:
    """
    Детектит признаки автопостинга (боты, агрегаторы)

    Возвращает:
        {
            "is_autopost": bool,
            "autopost_confidence": float (0-1),
            "reasons": list[str]
        }
    """
    if not posts or len(posts) < 5:
        return {"is_autopost": False, "autopost_confidence": 0.0, "reasons": []}

    reasons = []
    score = 0.0

    # Проверка 1: Посты в одно и то же время
    post_times = []
    for post in posts[:20]:
        if hasattr(post, 'date') and post.date:
            post_times.append(post.date.hour * 60 + post.date.minute)

    if len(post_times) >= 5:
        # Группируем по 30-минутным окнам
        time_buckets = {}
        for t in post_times:
            bucket = t // 30
            time_buckets[bucket] = time_buckets.get(bucket, 0) + 1

        max_bucket = max(time_buckets.values()) if time_buckets else 0
        if max_bucket >= len(post_times) * 0.6:  # 60%+ постов в одном окне
            score += 0.4
            reasons.append("posts_same_time")

    # Проверка 2: Маркеры автопостинга в тексте
    autopost_found = False
    for post in posts[:10]:
        if not hasattr(post, 'message') or not post.message:
            continue
        text_lower = post.message.lower()
        for marker in AUTOPOST_MARKERS:
            if marker in text_lower:
                autopost_found = True
                break
        if autopost_found:
            break

    if autopost_found:
        score += 0.5
        reasons.append("autopost_markers")

    # Проверка 3: Очень короткие посты (< 100 символов) + ссылки
    short_with_links = 0
    for post in posts[:20]:
        if not hasattr(post, 'message') or not post.message:
            continue
        if len(post.message) < 100 and ("http" in post.message or "t.me" in post.message):
            short_with_links += 1

    if short_with_links >= len(posts) * 0.5:  # 50%+ коротких с ссылками
        score += 0.3
        reasons.append("short_posts_with_links")

    is_autopost = score >= 0.5

    return {
        "is_autopost": is_autopost,
        "autopost_confidence": min(score, 1.0),
        "reasons": reasons
    }
