"""
Классификация каналов
"""
import re
from typing import Any
from telethon.tl.types import Message
from keywords import (
    EXPERT_MARKERS, NEWS_MARKERS, MEDIA_MARKERS, BRAND_MARKERS,
    AGGREGATOR_MARKERS, COMMUNITY_MARKERS, BLACKLIST_MARKERS,
    INTENT_MARKERS, AT_RE, extract_links
)


def _count_markers(text: str, markers: list[str]) -> int:
    """Считает количество маркеров в тексте"""
    return sum(1 for m in markers if m in text)


def _count_blacklist(text: str) -> tuple[int, str]:
    """Считает blacklist маркеры и возвращает топ категорию"""
    cats: dict[str, int] = {}
    for m, cat in BLACKLIST_MARKERS:
        if m in text:
            cats[cat] = cats.get(cat, 0) + 1
    total = sum(cats.values())
    if not cats:
        return 0, ""
    top = max(cats, key=cats.get)
    return total, top


def classify_channel(title: str, about: str, posts: list[Message], pinned_text: str) -> dict[str, Any]:
    """Классифицирует канал и определяет признаки экспертности"""
    parts = [title.lower(), about.lower(), (pinned_text or "").lower()]
    for m in posts[:10]:
        if m.message:
            parts.append(m.message.lower())
    text = "\n".join(parts)

    counts = {
        "expert": _count_markers(text, EXPERT_MARKERS),
        "news": _count_markers(text, NEWS_MARKERS),
        "media": _count_markers(text, MEDIA_MARKERS),
        "brand": _count_markers(text, BRAND_MARKERS),
        "aggregator": _count_markers(text, AGGREGATOR_MARKERS),
        "community": _count_markers(text, COMMUNITY_MARKERS),
    }

    bl_count, bl_top = _count_blacklist(text)
    blacklist_hit = bl_count >= 2
    bl_to_type = {"brand": "brand", "shop": "brand", "aggregator": "aggregator", "news": "news"}

    max_v = max(counts.values())
    if blacklist_hit:
        channel_type = bl_to_type.get(bl_top, "brand")
    elif max_v == 0:
        channel_type = "unknown"
    elif counts["expert"] == max_v:
        channel_type = "expert"
    else:
        channel_type = max(counts, key=counts.get)

    if blacklist_hit:
        is_expert = False
    else:
        is_expert = (
            counts["expert"] >= 2
            and counts["expert"] >= counts["news"]
            and counts["expert"] >= counts["brand"]
            and counts["expert"] >= counts["aggregator"]
            and channel_type in ("expert", "community", "unknown")
        )

    has_consulting = any(k in text for k in ["консультац", "разбор", "созвон", "индивидуальн", "сессия"])
    has_course = any(k in text for k in ["курс", "обучение", "тренинг", "наставничеств", "интенсив", "вебинар", "марафон", "школ"])
    has_testimonials = any(k in text for k in ["отзыв", "кейс", "результат ученик", "ученики говорят"])
    has_personal_brand = any(k in text for k in ["меня зовут", "мой опыт", "я психолог", "я нутрициолог", "я коуч", "я наставник", "я эксперт"])
    has_external = bool(extract_links(text))

    author_contact = "unknown"
    m_at = AT_RE.search(about or "")
    if m_at:
        author_contact = "@" + m_at.group(1)

    author_name = "unknown"
    m_name = re.search(r"[Мм]еня зовут\s+([А-ЯЁA-Z][а-яёa-z]+)", about or "")
    if m_name:
        author_name = m_name.group(1)

    intent_hits = sum(1 for k in INTENT_MARKERS if k in text)

    return {
        "channel_type": channel_type,
        "is_expert_channel": bool(is_expert),
        "author_name": author_name,
        "author_contact": author_contact,
        "has_external_links": "True" if has_external else "False",
        "has_consulting_offer": "True" if has_consulting else "unknown",
        "has_course_offer": "True" if has_course else "unknown",
        "has_testimonials": "True" if has_testimonials else "unknown",
        "has_personal_brand": "True" if has_personal_brand else "unknown",
        "blacklist_hit": blacklist_hit,
        "blacklist_top": bl_top,
        "expert_marker_count": counts["expert"],
        "intent_hits": intent_hits,
    }
