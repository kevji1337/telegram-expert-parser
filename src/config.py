"""Конфигурация парсера"""
import os
from typing import Any
from dotenv import load_dotenv

load_dotenv()

SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

TG_ACCOUNTS_STR = os.getenv("TG_ACCOUNTS", "")
if TG_ACCOUNTS_STR:
    TG_ACCOUNTS = [acc.strip() for acc in TG_ACCOUNTS_STR.split(",") if acc.strip()]
    ACCOUNT_CONFIGS: dict[str, dict[str, Any]] = {}
    for acc in TG_ACCOUNTS:
        api_id = os.getenv(f"TG_API_ID_{acc}")
        api_hash = os.getenv(f"TG_API_HASH_{acc}")
        if api_id and api_hash:
            ACCOUNT_CONFIGS[acc] = {"api_id": int(api_id), "api_hash": api_hash, "session": os.path.join(SESSIONS_DIR, acc)}
    if not ACCOUNT_CONFIGS:
        raise SystemExit("TG_ACCOUNTS задан, но ни один аккаунт не сконфигурирован в .env")
    print(f"[+] Режим автосвапа: {len(ACCOUNT_CONFIGS)} аккаунтов ({', '.join(ACCOUNT_CONFIGS.keys())})")
else:
    API_ID = int(os.getenv("TG_API_ID") or "0")
    API_HASH = os.getenv("TG_API_HASH") or ""
    SESSION_NAME = os.getenv("TG_SESSION", "tg_parser")
    if not API_ID or not API_HASH:
        raise SystemExit("Заполни TG_API_ID и TG_API_HASH в .env")
    ACCOUNT_CONFIGS = {"default": {"api_id": API_ID, "api_hash": API_HASH, "session": os.path.join(SESSIONS_DIR, SESSION_NAME)}}
    TG_ACCOUNTS = ["default"]
    print(f"[+] Режим одного аккаунта (session={SESSION_NAME})")

KEYWORDS_FILE = "keywords.yaml"

RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

OUTPUT_CSV = os.path.join(RESULTS_DIR, "telegram_channels_analysis_sorted.csv")
OUTPUT_SHORTLIST_CSV = os.path.join(RESULTS_DIR, "telegram_channels_shortlist.csv")
OUTPUT_DECOMP_CSV = os.path.join(RESULTS_DIR, "telegram_channels_decomposition.csv")
SEARCH_CACHE_FILE = "search_cache.json"
CHANNEL_CACHE_FILE = "channel_cache.json"
PROGRESS_FILE = "progress.json"

SEARCH_LIMIT_PER_KEYWORD = 50
POSTS_TO_ANALYZE = 20
MIN_PARTICIPANTS = 3000
DELAY_BETWEEN_CHANNELS_SEC = 0.35
SLEEP_BETWEEN_KEYWORDS_SEC = 2.0
FLOOD_WAIT_MAX_SEC = 600
FLOOD_WAIT_SWITCH_THRESHOLD = 300  # Переключаться на другой акк если FloodWait > 5 мин
CHECKPOINT_EVERY_N_CHANNELS = 25

MIN_AVG_VIEWS = 350
SMALL_CHANNEL_THRESHOLD = 5000
MIN_VIEW_RATIO_SMALL = 0.15
MIN_VIEW_RATIO_BIG = 0.10
MAX_ENGAGEMENT_PERCENT = 10.0
MAX_DAYS_SINCE_LAST_POST = 14
MIN_POSTS_PER_WEEK = 2

SEARCH_CACHE_TTL_DAYS = 3
CHANNEL_CACHE_TTL_DAYS = 7

class FloodWaitTooLong(Exception):
    pass
