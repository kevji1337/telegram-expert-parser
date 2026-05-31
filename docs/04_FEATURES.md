# Реализованные фичи

## ✅ Базовый парсинг

- Поиск каналов по ключевым словам через `SearchRequest`
- Получение полной информации: `GetFullChannelRequest`
- Последние 20 постов через `iter_messages`
- Закреплённое сообщение
- Извлечение ссылок и упоминаний из текста

## ✅ Метрики

- Средний и медианный охват (за все 20 постов + за 24h-постом)
- ERR = avg_views / subs * 100
- ERR24 = adv_post_reach_24h / subs * 100
- views/subs ratio (с разными порогами для малых/больших каналов)
- Реакции и комментарии (медианы)
- Постов в неделю
- Дней с последнего поста

## ✅ Классификация

- 6 типов канала: expert / news / brand / community / aggregator / unknown
- Blacklist-маркеры (магазины, новости, агрегаторы)
- Извлечение автора и контакта (`@username` в about/pinned)
- Детект offer-маркеров: consulting, course, testimonials, personal_brand

## ✅ Анализ ссылок

- Детект платформ: YouTube, Instagram, GetCourse, Taplink, Calendly, Tally, Stripe, Boosty, Patreon
- Группы: `has_youtube`, `has_getcourse`, `has_calendly`, `has_forms`, `has_payment`, `has_booking`
- Сохранение всех внешних ссылок (до 10) в `external_links`

## ✅ Анализ упоминаний

- Парсинг `@username` и `t.me/username` из about + pinned + 10 постов
- Сохранение до 20 упоминаний в `mentioned_channels`
- Используется для рекурсивного поиска (см. ниже)

## ✅ Качество отбора

- **1-е лицо** (`analyze_first_person_voice`): счётчик личных местоимений и глаголов, плотность, флаг `has_strong_voice`
- **CTA** (`analyze_cta_markers`): счёт призывов к действию, флаг `has_strong_cta`
- **Структура постов** (`analyze_post_structure`): детект серий, рубрик, консистентности формата
- **Автопостинг** (`detect_autoposting`): confidence по времени постов, маркерам, длине; штраф -50% к expert_score
- **Топ-пост**: ссылка на пост с максимальными просмотрами

## ✅ Скоринг и приоритезация

- 3 разных скора: `expert_score`, `monetization_score`, `analysis_queue_score`
- Buckets: `ANALYZE` / `RESERVE` / `IGNORE`
- Priority status A/B/C/D
- `false_positive_reason` для отсечения шума
- `top_signals` — компактная строка с ключевыми флагами (для UI)

## ✅ Расширение поиска

- **Рекурсивный поиск** (`RecursiveSearchQueue`): после первого прохода идёт второй — обрабатываются упоминания из найденных экспертных каналов
- **Кросс-промо детект**: ищет взаимные упоминания между каналами (формирует "сети")
- **Парсинг комментариев** (`fetch_comments_from_posts`): топ-5 постов, до 10 комментов с каждого — для будущего sentiment по аудитории

## ✅ Аналитика

- **Growth rate**: % роста подписчиков в день (через SQLite-историю)
- **Sentiment**: -1..+1 по позитивным/негативным словам в постах + about + pinned
- **Topic clusters**: топ-5 частотных слов в постах (черновая реализация)

## ✅ Надёжность

- **SQLite-кэш** вместо JSON: search_cache (TTL 3 дня), channel_cache (TTL 7 дней)
- **Адаптивный rate-limiter**: 0.1–5.0 сек, увеличивает задержку после ошибок, уменьшает после успехов
- **Multi-account auto-swap**: при FloodWait > 5 мин переключается на следующий аккаунт
- **Чекпоинты**: сохранение CSV каждые 25 обработанных каналов
- **Resume after crash**: `progress.json` хранит индекс последней ниши и ключа

## ✅ Производительность (модуль готов, не везде заюзан)

`performance.py`:
- `PriorityChannelQueue` (heap-based, обрабатывает каналы с высоким потенциалом первыми)
- `parallel_process_channels` (semaphore-ограниченная параллельная обработка)
- `IncrementalUpdater` (пересканирует только устаревшие каналы)
- `MultiAccountPool` (распределение нагрузки между аккаунтами)
- `BatchSaver` (буферизация записи CSV)
- `split_keywords_across_accounts` (round-robin распределение ключей)

## ✅ Веб-панель

- Flask на http://localhost:5000
- Тёмная/светлая темы (CSS variables, переключение в sidebar)
- Sidebar-навигация: Каналы / Шортлист / Декомпозиция / Парсер / Скачать
- **Главная**: таблица с фильтрами (поиск, приоритет, ниша, тип, мин. подписчиков/скор, expert-only, no_fp)
- **Шортлист и декомпозиция**: карточки с детальными метриками
- **Детальная страница канала**: все метрики + about + pinned + ссылки + упоминания
- **Запуск парсера**: страница с кнопками Start/Stop, live-консоль с подсветкой, статус-pill
- API: `/api/parser/start`, `/api/parser/stop`, `/api/parser/status`, `/api/parser/logs`
- Скачивание CSV: `/download/full`, `/download/shortlist`, `/download/decomp`
