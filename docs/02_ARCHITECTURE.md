# Архитектура и модули

## Структура репозитория

```
TG_Parser/
├── run.py                      Точка входа CLI
├── run_web.py                  Точка входа веб-панели
├── keywords.yaml               Ниши и ключевые слова
├── requirements.txt            telethon, flask, pyyaml
├── .env                        Креды Telegram (НЕ в git)
├── .gitignore
├── README.md
├── docs/                       Эта документация
├── results/                    Выходные CSV (gitignored)
│   ├── telegram_channels_analysis_sorted.csv
│   ├── telegram_channels_shortlist.csv
│   └── telegram_channels_decomposition.csv
├── sessions/                   Telethon-сессии (gitignored, секретно!)
├── archive/                    Старые версии (монолит)
└── src/
    ├── main.py                 Основной асинхронный цикл парсера
    ├── config.py               Все константы + загрузка .env
    ├── models.py               ChannelRow dataclass
    ├── cache.py                Загрузка niches/progress (YAML/JSON)
    ├── sqlite_cache.py         SQLite-кэш поиска и каналов (TTL)
    ├── rate_limiter.py         Адаптивный rate-limiter
    ├── telegram_client.py      Обёртки над Telethon API
    ├── metrics.py              Расчёт avg_views, median, posts_per_week
    ├── classification.py       Определение типа канала (expert/news/brand/...)
    ├── keywords.py             Маркеры + анализаторы (1-е лицо, CTA, структура, autopost)
    ├── scoring.py              Скоринг (expert_score, monetization, AQ score)
    ├── analytics.py            Sentiment, growth_rate, topic clusters
    ├── recursive_search.py     Очередь рекурсивного поиска по упоминаниям
    ├── performance.py          PriorityQueue, parallel processing, multi-account pool
    ├── parser_runner.py        Запуск парсера в фоне для веб-панели
    ├── export.py               Сохранение CSV
    └── web/
        ├── app.py              Flask-приложение
        └── templates/
            ├── base.html       Базовый шаблон (sidebar, темы)
            ├── index.html      Таблица всех каналов с фильтрами
            ├── shortlist.html  Карточки шортлиста
            ├── channel.html    Детальная страница канала
            └── parser.html     Управление парсером + live-консоль
```

## Зависимости между модулями

```
main.py
├── config (константы)
├── models (ChannelRow)
├── cache (niches, progress)
├── sqlite_cache (SQLiteCache)
├── rate_limiter (AdaptiveRateLimiter)
├── telegram_client (search_channels, fetch_*)
├── metrics (calc_metrics)
├── classification (classify_channel)
├── scoring (evaluate, calc_*_score, calc_priority, build_top_signals)
├── keywords (classify_keyword_quality, analyze_*, extract_*)
├── analytics (calc_growth_rate, analyze_sentiment)
├── recursive_search (RecursiveSearchQueue)
└── export (save_csv)

web/app.py
├── config (пути CSV)
├── parser_runner (запуск/стоп/логи)
└── (читает CSV напрямую)
```

## Хранилища данных

| Файл / БД | Что хранит | TTL | gitignore |
|-----------|------------|-----|-----------|
| `cache.db` | SQLite: результаты поиска по ключу, GetFullChannel | 3/7 дней | да |
| `progress.json` | Текущий индекс ниши и ключа (resumable) | — | да |
| `sessions/*.session` | Telethon-сессии (логин Telegram) | — | да (секрет!) |
| `results/*.csv` | Финальные результаты парсинга | — | да |
| `keywords.yaml` | Конфиг ниш и ключей | — | нет |
| `.env` | TG_API_ID, TG_API_HASH, TG_ACCOUNTS | — | да |

## Аккаунты Telegram

Поддерживается несколько аккаунтов (multi-account auto-swap):
- В `.env` указывается `TG_ACCOUNTS=acc1,acc2,acc3`
- Для каждого: `TG_API_ID_acc1=...`, `TG_API_HASH_acc1=...`
- При `FloodWait > 5 мин` автоматически переключается на следующий аккаунт
- Прогресс сохраняется → продолжает с того же ключа после свапа
