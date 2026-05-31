# История разработки

## Этапы развития проекта

### Этап 1 — Монолит (изначально)

Один файл `tg_channels_parser_telethon.py` >1000 строк со всей логикой:
- Поиск, классификация, метрики, скоринг, экспорт — всё в одном месте
- JSON-кэш (`search_cache.json`, `channel_cache.json`)
- Один аккаунт без свапа

Сейчас в `archive/` для истории.

### Этап 2 — Модульная разбивка

Файл разбит на модули в `src/`:
- `config`, `models`, `cache`, `keywords`, `classification`, `metrics`, `scoring`, `export`, `telegram_client`, `main`

Точка входа `run.py` импортит `main()` из `src/main.py`.

### Этап 3 — Новые ниши + intent-ключи

- Ниши заменены на **AI / IT / Бизнес-консалтинг**
- В `keywords.py` появилось разделение: `STRONG_KEYWORDS`, `INTENT_KEYWORDS`, `WEAK_KEYWORDS`
- `classify_keyword_quality` возвращает `strong / medium / weak`
- В `expert_score` бонусы за intent-маркеры и intent-ключи поиска

### Этап 4 — Детект внешних ссылок

- Добавлен `analyze_external_links` с детектом 8 платформ (YouTube, Instagram, GetCourse, Taplink, Calendly, формы, платежи, бронирование)
- В `ChannelRow` поля `has_youtube`, `has_getcourse`, ..., `external_links`
- Бонусы в `expert_score` за GetCourse / Calendly / forms

### Этап 5 — Парсинг упоминаний

- `extract_mentions` — `@username` и `t.me/username`
- Поле `mentioned_channels`

### Этап 6 — Надёжность (SQLite + adaptive rate limiter)

- Замена JSON-кэша на SQLite (`sqlite_cache.py`)
- TTL-кэш с автоинвалидацией
- `AdaptiveRateLimiter` — задержка скользит от 0.1 до 5.0 сек
- `FLOOD_WAIT_SWITCH_THRESHOLD = 300` — раньше переключаем аккаунт

### Этап 7 — Качество отбора

Добавлены анализаторы в `keywords.py`:
- `analyze_first_person_voice`
- `analyze_cta_markers`
- `analyze_post_structure`
- `detect_autoposting`

И аналогичные поля в `ChannelRow` + бонусы/штрафы в `expert_score`.

### Этап 8 — Расширение поиска + аналитика

- `recursive_search.py` с `RecursiveSearchQueue` и детектом кросс-промо
- `fetch_comments_from_posts` для парсинга комментов
- `analytics.py`: `calc_growth_rate`, `analyze_sentiment`, `detect_topic_clusters`

### Этап 9 — Производительность

Создан `performance.py`:
- `PriorityChannelQueue` (heap)
- `parallel_process_channels` (semaphore)
- `IncrementalUpdater`
- `MultiAccountPool`
- `BatchSaver`

(Пока не везде интегрировано в `main.py` — см. roadmap.)

### Этап 10 — Веб-панель

- Flask-приложение `src/web/app.py`
- Шаблоны: `base.html`, `index.html`, `shortlist.html`, `channel.html`, `parser.html`
- Сайдбар, тёмная/светлая тема, фильтры, поиск, детальные страницы
- `parser_runner.py` — запуск парсера в фоновом потоке с перехватом stdout
- API `/api/parser/{start,stop,status,logs}` для управления из браузера

### Этап 11 — Чистка и документация

- `src/main_backup.py` → `archive/`
- Удалены `__pycache__`, неиспользуемые JSON-кэши
- `src/cache.py` почищен (убраны legacy функции)
- Папка `results/` для CSV
- `docs/` с этой документацией

## Уроки

1. **JSON-кэш не масштабируется** — при 10k+ каналов парсинг JSON-файла занимает заметное время. SQLite сразу.
2. **Адаптивный rate-limiter > фиксированный** — Telegram капризный, лучше подстраиваться по обратной связи.
3. **Multi-account auto-swap критичен** — FloodWait > 5 мин ломает работу на часы. Лучше иметь резерв.
4. **Веб-панель сильно ускоряет анализ** — листать 200 каналов в Excel мучительно, в браузере с фильтрами в разы быстрее.
5. **Качественные сигналы > количественные** — 1-е лицо, CTA, структура постов — лучшие индикаторы экспертности, чем просто высокий охват.
6. **Рекурсивный поиск находит "невидимые" каналы** — те, что не вылазят по ключам, но рекомендуются через упоминания.

## Решения, которые не сработали

- **`load_cache` с TTL на mtime файла** — не учитывает per-entry TTL → перешли на SQLite с per-row timestamp
- **Универсальный `delay = 2.0 sec`** — то слишком медленно, то ловишь FloodWait → adaptive
- **Запуск парсера через subprocess из веба** — теряли stdout, не было контроля → перешли на threading с asyncio loop
- **Сохранение всех найденных ссылок** — переполняло CSV → ограничили топ-10 внешних, исключили `t.me/`
