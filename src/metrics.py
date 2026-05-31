"""
Расчет метрик каналов
"""
import statistics
from datetime import datetime, timezone, timedelta
from telethon.tl.types import Message


def calc_metrics(posts: list[Message], channel_username: str) -> dict:
    """Считает метрики по постам канала"""
    if not posts:
        return {
            "avg_views": 0.0, "avg_views_24h": 0.0, "avg_reactions": 0.0, "avg_comments": 0.0,
            "median_views": 0.0, "median_views_24h": 0.0, "median_reactions": 0.0, "median_comments": 0.0,
            "posts_per_week": 0.0, "last_post_dt": None, "links": [],
        }

    now = datetime.now(tz=timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    views_sum = 0
    views_24h_sum = 0
    views_24h_n = 0
    reactions_sum = 0
    reactions_n = 0
    comments_sum = 0
    comments_n = 0

    views_list: list[int] = []
    views_24h_list: list[int] = []
    reactions_list: list[int] = []
    comments_list: list[int] = []
    links: list[str] = []
    dates: list[datetime] = []

    uname = channel_username.lstrip("@")

    for m in posts:
        if m.date:
            dt = m.date.replace(tzinfo=timezone.utc) if m.date.tzinfo is None else m.date
            dates.append(dt)

        if m.views is not None:
            v = int(m.views)
            views_sum += v
            views_list.append(v)
            if m.date and m.date >= cutoff_24h:
                views_24h_sum += v
                views_24h_n += 1
                views_24h_list.append(v)

        if m.reactions and m.reactions.results:
            total = int(sum(r.count for r in m.reactions.results))
            reactions_sum += total
            reactions_n += 1
            reactions_list.append(total)

        if m.replies is not None:
            c = int(m.replies.replies or 0)
            comments_sum += c
            comments_n += 1
            comments_list.append(c)

        if uname and m.id:
            links.append(f"https://t.me/{uname}/{m.id}")

    n = len(posts)
    avg_views = views_sum / n if n else 0
    avg_views_24h = views_24h_sum / views_24h_n if views_24h_n else 0
    avg_reactions = reactions_sum / reactions_n if reactions_n else 0
    avg_comments = comments_sum / comments_n if comments_n else 0

    median_views = float(statistics.median(views_list)) if views_list else 0.0
    median_views_24h = float(statistics.median(views_24h_list)) if views_24h_list else 0.0
    median_reactions = float(statistics.median(reactions_list)) if reactions_list else 0.0
    median_comments = float(statistics.median(comments_list)) if comments_list else 0.0

    if len(dates) >= 2:
        dates.sort()
        span_days = max(1, (dates[-1] - dates[0]).total_seconds() / 86400)
        posts_per_week = n / span_days * 7
    else:
        posts_per_week = 0.0

    return {
        "avg_views": avg_views, "avg_views_24h": avg_views_24h,
        "avg_reactions": avg_reactions, "avg_comments": avg_comments,
        "median_views": median_views, "median_views_24h": median_views_24h,
        "median_reactions": median_reactions, "median_comments": median_comments,
        "posts_per_week": posts_per_week, "last_post_dt": max(dates) if dates else None,
        "links": links[:10],
    }
