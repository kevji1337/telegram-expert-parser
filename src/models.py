"""
Модель данных для строки CSV
"""
from dataclasses import dataclass


@dataclass
class ChannelRow:
    title: str = ""
    username: str = ""
    link: str = ""
    about: str = ""

    niche_key: str = ""
    niche_title: str = ""
    matched_niches: str = ""
    matched_keywords: str = ""

    channel_type: str = "unknown"
    is_expert_channel: bool = False
    expert_score: int = 0
    priority_status: str = ""
    monetization_score: int = 0
    is_suitable: bool = False
    reason: str = ""
    false_positive_reason: str = ""
    keyword_match_quality: str = "weak"

    analysis_queue_score: int = 0
    analysis_priority: str = "IGNORE"
    final_rank: int = 0
    selected_for_manual_analysis: bool = False
    selected_for_decomposition: bool = False

    participants_count: int = 0
    avg_post_reach: int = 0
    adv_post_reach_24h: int = 0
    avg_views_last_posts: float = 0.0
    err_percent: float = 0.0
    err24_percent: float = 0.0
    view_to_subs_ratio: float = 0.0
    avg_reactions: float = 0.0
    avg_comments: float = 0.0
    engagement_percent: float = 0.0
    posts_per_week: float = 0.0
    last_post_date: str = ""
    days_since_last_post: int = 0
    suspicious_spike: bool = False
    last_post_links: str = ""

    pinned_text: str = ""
    pinned_links: str = ""

    author_name: str = "unknown"
    author_contact: str = "unknown"
    has_external_links: str = "unknown"
    has_consulting_offer: str = "unknown"
    has_course_offer: str = "unknown"
    has_testimonials: str = "unknown"
    has_personal_brand: str = "unknown"

    is_verified: bool = False
    is_scam: bool = False
    is_fake: bool = False

    has_youtube: bool = False
    has_instagram: bool = False
    has_getcourse: bool = False
    has_taplink: bool = False
    has_calendly: bool = False
    has_forms: bool = False
    has_payment: bool = False
    has_booking: bool = False
    external_links: str = ""
    mentioned_channels: str = ""

    # Качество отбора
    first_person_count: int = 0
    first_person_density: float = 0.0
    has_strong_voice: bool = False
    cta_count: int = 0
    has_strong_cta: bool = False
    has_series: bool = False
    has_rubrics: bool = False
    avg_post_length: int = 0
    has_consistent_format: bool = False
    is_autopost: bool = False
    autopost_confidence: float = 0.0

    # Аналитика
    growth_rate: float = 0.0
    top_post_views: int = 0
    top_post_link: str = ""
    sentiment_score: float = 0.0
    comment_sentiment_score: float = 0.0

    top_signals: str = ""

    manual_review_status: str = "не смотрел"
