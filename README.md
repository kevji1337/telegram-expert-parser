# TG_Parser — Поиск экспертных Telegram-каналов для монетизации

## Структура проекта

```
TG_Parser/
├── src/                    # Исходный код (модули)
│   ├── config.py          # Конфигурация и константы
│   ├── models.py          # Модель данных (ChannelRow)
│   ├── keywords.py        # Маркеры и классификация ключевых слов
│   ├── cache.py           # Кэши и прогресс
│   ├── sqlite_cache.py    # SQLite кэш (замена JSON)
│   ├── rate_limiter.py    # Адаптивный rate limiter
│   ├── telegram_client.py # Работа с Telegram API
│   ├── metrics.py         # Расчет метрик каналов
│   ├── classification.py  # Классификация каналов
│   ├── scoring.py         # Скоринг и оценка
│   ├── export.py          # Экспорт в CSV
│   └── main.py            # Главный модуль
├── run.py                 # Точка входа для запуска
├── keywords.yaml          # Ниши и ключевые слова
├── .env                   # Настройки (API ключи)
├── cache.db               # SQLite кэш (создаётся автоматически)
└── sessions/              # Telethon сессии

```

## Что делает парсер

- Ищет каналы по ключевым словам из `keywords.yaml` (сейчас: AI, IT, Бизнес-консалтинг)
- Собирает метрики: подписчики, просмотры (медиана), реакции, комменты, ERR, частота постинга
- Анализирует закреп (pinned post) и извлекает ссылки
- **Детектит внешние платформы**: YouTube, Instagram, GetCourse, Taplink, Calendly, формы, платёжные системы
- **Парсит упоминания** других каналов (@username, t.me/...) из постов
- Классифицирует канал (expert/media/brand/aggregator/news/community)
- Считает **expert_score** (0-100) с бонусами:
  - Intent-ключи ("курсы по ИИ", "бизнес консультант") → +10-20 баллов
  - GetCourse → +10 баллов
  - Calendly/бронирование → +8 баллов
  - Формы (Google Forms, Typeform) → +5 баллов
- Делает автоотбор:
  - **топ-20** на ручной анализ (`selected_for_manual_analysis`)
  - **топ-5** на глубокую декомпозицию (`selected_for_decomposition`)

## Как запустить

```bash
python -m venv .venv
.venv\Scripts\activate
pip install telethon python-dotenv pyyaml
python run.py
```

## Настройка .env

Смотри `.env.example`. Поддержка нескольких аккаунтов:

```env
TG_ACCOUNTS=+375291234567,+375291111111,+375292222222

TG_API_ID_+375291234567=12345678
TG_API_HASH_+375291234567=abcdef...

TG_API_ID_+375291111111=87654321
TG_API_HASH_+375291111111=fedcba...
```

## Выходные файлы

- `telegram_channels_analysis_sorted.csv` — полный отчёт (все каналы)
- `telegram_channels_shortlist.csv` — 20 каналов на ручной разбор
- `telegram_channels_decomposition.csv` — топ-5 на декомпозицию

## Важно

- `sessions/` содержит файлы авторизации Telethon (формат: `+375291234567.session`)
- `cache.db` — SQLite база для кэша (быстрее и надёжнее JSON)
- `progress.json` — чекпоинт (можно удалить для запуска "с нуля")
- **Intent-ключи** ("курсы по ИИ", "бизнес консультант") дают +10-20 баллов к expert_score
- **Адаптивный rate-limit**: автоматически подстраивается под лимиты Telegram
- **Ранний свап аккаунтов**: переключается на следующий акк при FloodWait > 5 мин

## Новые поля в CSV

- `external_links` — все внешние ссылки (не t.me), макс 10
- `mentioned_channels` — упоминания других каналов, макс 20
- `has_youtube`, `has_instagram`, `has_getcourse`, `has_calendly`, `has_forms`, `has_payment`, `has_booking`, `has_taplink` — флаги платформ

## Что улучшено

- **Модульная структура**: код разбит на 12 модулей вместо монолита
- **SQLite кэш**: быстрее и надёжнее JSON (не ломается при падении)
- **Адаптивный rate-limit**: автоматически замедляется при ошибках, ускоряется при успехе
- **Ранний свап аккаунтов**: переключается при FloodWait > 300s (вместо 600s)
- **Устойчивые метрики**: просмотры/реакции/комменты по медиане (меньше влияния выбросов)
- **Анализ закрепа**: текст и ссылки из pinned post
- **Детект внешних ссылок**: YouTube, Instagram, GetCourse, Calendly, формы
- **Парсинг упоминаний**: извлекает @username и t.me/... из постов
- **Intent-маркеры**: приоритет каналам с офферами/курсами/консультациями
- **Progress resume**: автовозобновление после FloodWait/падений
- **Анализ закрепа**: текст и ссылки из pinned post
- **Intent-маркеры**: приоритет каналам с офферами/курсами/консультациями
- **Progress resume**: автовозобновление после FloodWait/падений
- **Автосвап аккаунтов**: при FloodWait >600s переключается на следующий аккаунт
