# TG_Parser — Поиск экспертных Telegram-каналов

Парсер для поиска и оценки Telegram-каналов экспертов, продавцов курсов и B2B-офферов. Считает метрики, скорит, классифицирует и собирает шортлист на ручной анализ. Есть веб-панель с дашбордом, управлением парсером и Telegram-аккаунтами.

## Возможности

- Поиск по нишам из `keywords.yaml` (AI, IT, бизнес-консалтинг и др.)
- Парсинг метрик: подписчики, просмотры (медиана), реакции, комментарии, ERR, частота постинга
- Анализ закреп-поста и внешних ссылок (YouTube, Instagram, GetCourse, Calendly, формы, платежи, бронирование)
- Парсинг упоминаний других каналов (@username, t.me/...)
- Классификация: expert / media / brand / aggregator / news / community
- **Expert score 0-100** с бонусами за intent-ключи, GetCourse, Calendly, формы
- Sentiment-анализ автора и комментариев
- Автоотбор: топ-20 на ручной анализ, топ-5 на декомпозицию
- **Web UI**: таблица, фильтры, дашборд с графиками, управление парсером и аккаунтами

## Установка

### Требования

- Python 3.11+
- Telegram-аккаунт (api_id / api_hash с https://my.telegram.org/apps)

### Шаги

1. **Клонируй репозиторий**

```bash
git clone https://github.com/<your-user>/TG_Parser.git
cd TG_Parser
```

2. **Создай виртуальное окружение и поставь зависимости**

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. **Создай `.env`** на основе `.env.example`:

```bash
cp .env.example .env       # Linux/macOS
copy .env.example .env     # Windows
```

Открой `.env` и заполни. Минимум один аккаунт:

```env
TG_ACCOUNTS=+375291234567

TG_API_ID_+375291234567=12345678
TG_API_HASH_+375291234567=abcdef0123456789abcdef0123456789
```

Получить `api_id` / `api_hash`: https://my.telegram.org/apps → "Create new application".

Для параллельного парсинга добавь несколько аккаунтов через запятую — парсер автоматически свапнется при FloodWait.

4. **Авторизуй сессии**

**Через web-панель (рекомендуется):**

```bash
python run_web.py
```

Открой http://localhost:5000/accounts → нажми **Войти** → введи код из Telegram → если нужно, пароль 2FA. Сессия сохранится в `sessions/`.

**Через консоль (альтернатива):**

```bash
python run.py
```

При первом запуске Telethon спросит код в терминале.

5. **Запусти парсинг**

Через web UI: http://localhost:5000/parser → **Запустить парсер**.

Или из консоли:
```bash
python run.py
```

Результаты появятся в `results/`.

## Структура проекта

```
TG_Parser/
├── run.py                 # CLI запуск парсера
├── run_web.py             # Запуск web-панели (http://localhost:5000)
├── requirements.txt
├── keywords.yaml          # Ниши и ключевые слова
├── .env                   # Секреты (не коммитим)
├── .env.example           # Шаблон
├── public/icon.png        # Иконка
├── sessions/              # Telethon .session файлы
├── results/               # CSV-отчёты
├── cache.db               # SQLite кэш
├── progress.json          # Чекпоинт парсера
└── src/
    ├── main.py            # Главный модуль парсера
    ├── config.py          # Настройки из .env
    ├── models.py          # ChannelRow dataclass
    ├── auth_manager.py    # Управление Telegram-сессиями для web UI
    ├── parser_runner.py   # Запуск парсера из web UI
    ├── telegram_client.py # Telegram API через Telethon
    ├── metrics.py         # Метрики каналов
    ├── classification.py  # Классификация
    ├── scoring.py         # Expert score
    ├── keywords.py        # Маркеры и intent-ключи
    ├── sqlite_cache.py    # SQLite кэш
    ├── rate_limiter.py    # Адаптивный rate limiter
    ├── recursive_search.py# Рекурсивный поиск
    ├── analytics.py       # Аналитика
    ├── performance.py     # Профайлинг
    ├── export.py          # Экспорт CSV
    └── web/               # Flask-панель
        ├── app.py
        └── templates/
```

## Web-панель

```bash
python run_web.py
```

- `/` — таблица всех каналов с фильтрами и сортировкой
- `/shortlist` — топ-20 на ручной анализ
- `/decomposition` — топ-5 на декомпозицию
- `/channel/<id>` — детальная карточка
- `/dashboard` — графики по нишам, типам, expert-score, росту, топ растущих
- `/parser` — запуск/остановка парсера, логи в реальном времени
- `/accounts` — Telegram-аккаунты: проверка сессий, login, удаление, добавление новых

## Выходные файлы (`results/`)

- `telegram_channels_analysis_sorted.csv` — полный отчёт (все каналы)
- `telegram_channels_shortlist.csv` — топ-20 на ручной разбор
- `telegram_channels_decomposition.csv` — топ-5 на декомпозицию

## Ключевые поля CSV

- `participants_count`, `median_views`, `avg_reactions`, `avg_comments`, `err_percent`, `posts_per_week`
- `growth_rate` — рост за день в %
- `expert_score` 0-100 — суммарный балл "экспертности"
- `analysis_queue_score` — итоговый скор для сортировки
- `analysis_priority` — ANALYZE / RESERVE / IGNORE
- `channel_type` — expert / media / brand / aggregator / news / community
- `sentiment_score`, `comment_sentiment_score` — тональность автора и комментаторов
- `is_expert_channel`, `is_verified`, `is_scam`
- `selected_for_manual_analysis`, `selected_for_decomposition`
- `external_links`, `mentioned_channels` (до 10 / 20)
- `has_youtube`, `has_instagram`, `has_getcourse`, `has_calendly`, `has_forms`, `has_payment`, `has_booking`, `has_taplink`

## Конфигурация

Все настройки в `src/config.py`. Основные:

- `SEARCH_LIMIT_PER_KEYWORD = 50` — каналов на ключ
- `POSTS_TO_ANALYZE = 20` — постов для метрик
- `MIN_PARTICIPANTS = 3000` — минимум подписчиков
- `MIN_AVG_VIEWS = 350` — минимум медианных просмотров
- `MAX_DAYS_SINCE_LAST_POST = 14` — фильтр "мёртвых" каналов
- `FLOOD_WAIT_SWITCH_THRESHOLD = 300` — свапать аккаунт при FloodWait > 5 мин
- `PARALLEL_MODE` — авто-включается при 2+ аккаунтах

## Технические особенности

- Модульная архитектура: 15+ модулей в `src/`
- SQLite-кэш вместо JSON (быстрее, не теряет данные при падении)
- Адаптивный rate-limit: замедляется при ошибках, ускоряется при успехе
- Ранний свап аккаунтов при FloodWait > 300 с
- Устойчивые метрики: медиана, а не среднее (меньше выбросов)
- Progress resume: чекпоинт каждые N каналов, возобновление после падений
- Параллельный парсинг при наличии нескольких аккаунтов

## Безопасность

- `.env` и `sessions/` в `.gitignore` — секреты не уйдут в репозиторий
- Web-панель слушает `0.0.0.0:5000` — не выставляй наружу без обратного прокси и авторизации
- Auth flow на странице `/accounts` хранит коды Telegram и 2FA только в памяти, без логирования

## Лицензия

Для личного использования.
