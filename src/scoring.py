"""
Скоринг и оценка каналов
"""
from models import ChannelRow
from config import (
    MIN_AVG_VIEWS, SMALL_CHANNEL_THRESHOLD, MIN_VIEW_RATIO_SMALL,
    MIN_VIEW_RATIO_BIG, MAX_ENGAGEMENT_PERCENT, MAX_DAYS_SINCE_LAST_POST,
    MIN_POSTS_PER_WEEK
)


def _view_ratio_threshold(subs: int) -> float:
    """Возвращает порог views/subs в зависимости от размера канала"""
    return MIN_VIEW_RATIO_SMALL if subs <= SMALL_CHANNEL_THRESHOLD else MIN_VIEW_RATIO_BIG


def evaluate(row: ChannelRow) -> tuple[bool, str]:
    """Оценивает пригодность канала"""
    fails: list[str] = []
    oks: list[str] = []
    subs = row.participants_count or 1

    if row.avg_post_reach < MIN_AVG_VIEWS:
        fails.append(f"мало просмотров ({row.avg_post_reach} < {MIN_AVG_VIEWS})")
    else:
        oks.append(f"просмотры={row.avg_post_reach}")

    threshold = _view_ratio_threshold(subs)
    if row.view_to_subs_ratio < threshold:
        fails.append(f"низкое views/subs ({row.view_to_subs_ratio:.1%} < {threshold:.0%})")
    else:
        oks.append(f"views/subs={row.view_to_subs_ratio:.1%}")

    if row.engagement_percent > MAX_ENGAGEMENT_PERCENT:
        fails.append(f"подозрительная вовлечённость ({row.engagement_percent:.1f}% > {MAX_ENGAGEMENT_PERCENT}%)")

    if row.days_since_last_post > MAX_DAYS_SINCE_LAST_POST:
        fails.append(f"последний пост {row.days_since_last_post} дн. назад")

    if row.posts_per_week < MIN_POSTS_PER_WEEK:
        fails.append(f"редкие публикации ({row.posts_per_week:.1f}/нед < {MIN_POSTS_PER_WEEK})")

    suitable = not fails
    reason = " | ".join(oks) if suitable else "; ".join(fails)
    return suitable, reason


def calc_monetization_score(row: ChannelRow) -> int:
    """Считает скор монетизации"""
    score = 0
    subs = row.participants_count or 1
    if row.avg_post_reach >= MIN_AVG_VIEWS:
        score += 20
    if row.view_to_subs_ratio >= _view_ratio_threshold(subs):
        score += 20
    if 3.0 <= row.engagement_percent <= MAX_ENGAGEMENT_PERCENT:
        score += 20
    if row.avg_comments > 0:
        score += 15
    if row.days_since_last_post <= MAX_DAYS_SINCE_LAST_POST:
        score += 10
    if row.posts_per_week >= MIN_POSTS_PER_WEEK:
        score += 10
    if row.has_consulting_offer == "True" or row.has_course_offer == "True":
        score += 5
    return min(score, 100)


def calc_expert_score(row: ChannelRow, intent_hits: int, intent_keyword_count: int = 0) -> int:
    """Считает скор экспертности"""
    score = 0

    if row.avg_post_reach >= MIN_AVG_VIEWS:
        score += 15

    r = row.view_to_subs_ratio
    if r >= 0.30:
        score += 20
    elif r >= 0.20:
        score += 15
    elif r >= 0.10:
        score += 10

    if row.avg_comments > 10:
        score += 15
    elif row.avg_comments > 3:
        score += 10
    elif row.avg_comments > 0:
        score += 5

    if row.posts_per_week >= 3:
        score += 10
    elif row.posts_per_week >= 1:
        score += 5

    if row.days_since_last_post <= 7:
        score += 10
    elif row.days_since_last_post <= 14:
        score += 5

    if row.is_expert_channel:
        score += 30

    # бонус за наличие оффера/интента в тексте канала
    score += min(15, intent_hits * 3)

    # бонус за поиск по intent-ключам (канал найден по "курсы по ИИ" и т.п.)
    score += min(20, intent_keyword_count * 10)

    # НОВОЕ: бонус за "серьёзные" внешние ссылки (GetCourse, Calendly, формы)
    if row.has_getcourse:
        score += 10  # GetCourse = платформа курсов, сильный сигнал
    if row.has_calendly or row.has_booking:
        score += 8   # Бронирование = консультации/созвоны
    if row.has_forms:
        score += 5   # Формы = сбор заявок

    # НОВОЕ: бонус за "1-е лицо" (личный голос автора)
    if row.has_strong_voice:
        score += 10
    elif row.first_person_count >= 3:
        score += 5

    # НОВОЕ: бонус за продажные CTA
    if row.has_strong_cta:
        score += 12
    elif row.cta_count >= 2:
        score += 6

    # НОВОЕ: бонус за структурированный контент
    if row.has_series or row.has_rubrics:
        score += 8
    if row.has_consistent_format:
        score += 5

    # НОВОЕ: штраф за автопостинг
    if row.is_autopost:
        score = int(score * 0.5)  # -50% если бот/агрегатор

    if row.avg_comments < 1:
        score = min(score, 85)

    return min(score, 100)


def calc_analysis_queue_score(row: ChannelRow) -> int:
    """Считает скор для очереди анализа"""
    score = 0
    if row.avg_post_reach >= 3000:
        score += 40
    elif row.avg_post_reach >= 1000:
        score += 30
    elif row.avg_post_reach >= 300:
        score += 20

    r = row.view_to_subs_ratio
    if r >= 0.30:
        score += 30
    elif r >= 0.20:
        score += 20
    elif r >= 0.10:
        score += 10

    if row.avg_comments > 20:
        score += 30
    elif row.avg_comments > 5:
        score += 20
    elif row.avg_comments > 0:
        score += 10

    if row.is_expert_channel:
        score += 30

    if row.days_since_last_post <= 14:
        score += 10
    if row.posts_per_week >= 2:
        score += 10

    return min(score, 100)


def calc_analysis_priority(score: int) -> str:
    """Определяет приоритет анализа"""
    if score >= 70:
        return "ANALYZE"
    if score >= 50:
        return "RESERVE"
    return "IGNORE"


def calc_priority(row: ChannelRow) -> str:
    """Определяет приоритет канала (A/B/C/D)"""
    subs = row.participants_count or 1
    if row.avg_post_reach < MIN_AVG_VIEWS:
        return "D"
    if row.days_since_last_post > MAX_DAYS_SINCE_LAST_POST:
        return "D"
    if row.view_to_subs_ratio < _view_ratio_threshold(subs):
        return "D"
    if row.avg_comments <= 0:
        return "B" if row.monetization_score >= 60 or row.is_suitable else "C"
    if row.monetization_score >= 80 and row.is_suitable:
        return "A"
    if row.monetization_score >= 60:
        return "B"
    return "C"


def build_top_signals(row: ChannelRow) -> str:
    """Формирует список топ-сигналов канала"""
    s: list[str] = []
    if row.pinned_text:
        s.append("pin")
    if row.has_consulting_offer == "True":
        s.append("consulting")
    if row.has_course_offer == "True":
        s.append("course")
    if row.has_testimonials == "True":
        s.append("testimonials")
    if row.has_personal_brand == "True":
        s.append("personal_brand")
    if row.has_getcourse:
        s.append("getcourse")
    if row.has_calendly or row.has_booking:
        s.append("booking")
    if row.has_forms:
        s.append("forms")
    if row.has_youtube:
        s.append("youtube")
    if row.has_instagram:
        s.append("instagram")
    if row.has_strong_voice:
        s.append("1st_person")
    if row.has_strong_cta:
        s.append("strong_cta")
    if row.has_series or row.has_rubrics:
        s.append("structured")
    if row.is_autopost:
        s.append("autopost")
    if row.view_to_subs_ratio >= 0.2:
        s.append("err>=20%")
    if row.avg_comments > 3:
        s.append("comments>3")
    if row.days_since_last_post <= 7:
        s.append("fresh<=7d")
    if row.posts_per_week >= 2:
        s.append("freq>=2/w")
    return ",".join(s[:10])
