# Setup и использование

## Установка

```bash
# 1. Клонировать репозиторий
git clone <repo-url>
cd TG_Parser

# 2. Создать venv и поставить зависимости
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
```

`requirements.txt`:
- telethon ≥ 1.34.0
- pyyaml ≥ 6.0
- flask ≥ 3.0.0
- python-dotenv

## Конфигурация

### `.env` (создать в корне)

**Один аккаунт:**
```ini
TG_API_ID=12345678
TG_API_HASH=abcdef...
TG_SESSION=tg_parser
```

**Несколько аккаунтов (auto-swap при FloodWait):**
```ini
TG_ACCOUNTS=acc1,acc2,acc3
TG_API_ID_acc1=12345678
TG_API_HASH_acc1=abcdef...
TG_API_ID_acc2=22222222
TG_API_HASH_acc2=ghijkl...
TG_API_ID_acc3=33333333
TG_API_HASH_acc3=mnopqr...
```

API ID и Hash получаются на https://my.telegram.org → API Development Tools.

### Первый запуск — авторизация

```bash
python run.py
```

При первом запуске Telethon спросит номер телефона и код из SMS/Telegram для каждого аккаунта. Сессия сохранится в `sessions/<account_name>.session` — больше код вводить не нужно.

### `keywords.yaml` — настройка ниш

```yaml
niches:
  ai:
    title: "AI / Нейросети"
    keywords:
      - "нейросети"
      - "chatgpt"
      - "промптинг"
      - "обучение нейросетям"
  it:
    title: "IT / Программирование"
    keywords:
      - "программирование"
      - "курсы программирования"
  business:
    title: "Бизнес-консалтинг"
    keywords:
      - "наставничество"
      - "бизнес коуч"
```

## Запуск

### Парсер в CLI

```bash
python run.py
```

Что происходит:
1. Загружаются ниши из `keywords.yaml`
2. По каждой нише и ключу — поиск каналов
3. Каждый канал обрабатывается → запись в `seen` dict
4. Каждые 25 каналов — чекпоинт в `results/telegram_channels_analysis_sorted.csv`
5. После всех ключей — рекурсивный поиск по упоминаниям
6. Финальная сортировка → 3 CSV в `results/`

Прервать можно Ctrl+C — прогресс сохранится. При повторном запуске продолжит с того же ключа.

### Веб-панель

```bash
python run_web.py
```

Откроется на http://localhost:5000.

Страницы:
- `/` — все каналы с фильтрами
- `/shortlist` — топ-20 для ручного анализа
- `/decomposition` — топ-5 для декомпозиции
- `/parser` — запуск/остановка парсера + live-логи
- `/channel/<idx>` — детальная страница канала

## Тонкая настройка

В `src/config.py`:

| Константа | Смысл | Default |
|-----------|-------|---------|
| `MIN_PARTICIPANTS` | минимум подписчиков для обработки | 3000 |
| `MIN_AVG_VIEWS` | минимум средних просмотров для suitable | 350 |
| `SEARCH_LIMIT_PER_KEYWORD` | сколько каналов запрашивать через SearchRequest | 50 |
| `POSTS_TO_ANALYZE` | сколько последних постов парсить | 20 |
| `DELAY_BETWEEN_CHANNELS_SEC` | начальная задержка между каналами | 0.35 |
| `FLOOD_WAIT_SWITCH_THRESHOLD` | сек, после которого свапить аккаунт | 300 |
| `CHECKPOINT_EVERY_N_CHANNELS` | как часто сохранять CSV | 25 |
| `SMALL_CHANNEL_THRESHOLD` | граница "малого" канала | 5000 |
| `MIN_VIEW_RATIO_SMALL` | порог views/subs для малых | 0.15 |
| `MIN_VIEW_RATIO_BIG` | порог views/subs для больших | 0.10 |
| `MAX_ENGAGEMENT_PERCENT` | потолок подозрительной вовлечённости | 10.0 |
| `MAX_DAYS_SINCE_LAST_POST` | дней с последнего поста | 14 |
| `MIN_POSTS_PER_WEEK` | минимум постов в неделю | 2 |

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| `ModuleNotFoundError: telethon` | `pip install -r requirements.txt` |
| `Заполни TG_API_ID и TG_API_HASH в .env` | Создать `.env` (см. выше) |
| `FloodWait` слишком часто | Уменьшить `SEARCH_LIMIT_PER_KEYWORD`, увеличить `DELAY_BETWEEN_CHANNELS_SEC` |
| Веб-панель не видит результаты | Проверь, что CSV есть в `results/` |
| Парсер не стартует из веб-панели | Глянуть консоль `run_web.py` — может не подтянуться `.env` |
| `cache.db is locked` | Закрыть Studio/DB Browser; SQLite не любит конкурентные writes |

## Очистка

```bash
# Сбросить прогресс (начать с первой ниши)
del progress.json

# Сбросить кэш поиска (пересканировать всё заново)
del cache.db

# Удалить сессию аккаунта (нужно будет залогиниться снова)
del sessions\acc1.session
```
