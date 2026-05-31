# Алгоритмы классификации и скоринга

## Классификация типа канала (`classification.py`)

Каналу присваивается один из типов: `expert`, `news`, `brand`, `community`, `aggregator`, `unknown`.

Решение принимается по совокупности маркеров в `title + about + pinned + последние посты`:

- **EXPERT_MARKERS**: "меня зовут", "автор канал", "помогаю", "консультац", "наставничеств", "коуч", "ментор", "психолог", "нутрициолог", "отзыв", "кейсы", "созвон", "разбор", "запись"
- **NEWS_MARKERS**: "новости", "редакция", "сми", "издание", "пресс-служб"
- **BRAND_MARKERS**: "официальный канал", "интернет-магазин", "маркетплейс"
- **AGGREGATOR_MARKERS**: "подборк", "топ-", "сборник", "лучшее за", "агрегатор"
- **COMMUNITY_MARKERS**: "сообщество", "наш чат", "обсуждаем"

Дополнительно: `is_expert_channel = True` если найдено ≥2 expert-маркера И нет blacklist-маркеров.

## Скоринг (`scoring.py`)

### `expert_score` (0–100)
| Сигнал | Баллы |
|--------|-------|
| Охват ≥ MIN_AVG_VIEWS | +15 |
| views/subs ≥ 30% / 20% / 10% | +20 / +15 / +10 |
| Комменты >10 / >3 / >0 | +15 / +10 / +5 |
| Постов/нед ≥3 / ≥1 | +10 / +5 |
| Свежесть ≤7 / ≤14 дней | +10 / +5 |
| Канал классифицирован как expert | +30 |
| Intent-маркеры в тексте | +3 за каждый, до +15 |
| Intent-ключи (по которым нашли канал) | +10 за каждый, до +20 |
| Есть GetCourse | +10 |
| Есть Calendly/booking | +8 |
| Есть формы (Tally/Google Forms) | +5 |
| has_strong_voice (1-е лицо ≥5 и плотность ≥1%) | +10 |
| 1-е лицо ≥3 | +5 |
| has_strong_cta (≥3 CTA-маркера) | +12 |
| CTA ≥2 | +6 |
| has_series или has_rubrics | +8 |
| has_consistent_format | +5 |
| **is_autopost** | **×0.5 штраф** |

Кэп: avg_comments <1 → expert_score ≤ 85.

### `monetization_score` (0–100)
| Сигнал | Баллы |
|--------|-------|
| Охват ≥ MIN_AVG_VIEWS | +20 |
| views/subs выше порога | +20 |
| Вовлечённость 3–10% | +20 |
| Есть комменты | +15 |
| Свежие посты | +10 |
| Регулярная частота | +10 |
| Оффер (consulting/course) | +5 |

### `analysis_queue_score` (0–100)
- Охват ≥3000/1000/300 → +40/+30/+20
- views/subs ≥30%/20%/10% → +30/+20/+10
- Комменты >20/>5/>0 → +30/+20/+10
- Эксперт → +30
- Свежесть ≤14 дней → +10
- Регулярность ≥2/нед → +10

### `analysis_priority` (на основе AQ score)
- `ANALYZE` если ≥70
- `RESERVE` если ≥50
- `IGNORE` иначе

### `priority_status` (A/B/C/D)
- `D` если охват < MIN_AVG_VIEWS, или давно не публиковал, или низкий views/subs
- `A` если monetization ≥80 и suitable
- `B` если monetization ≥60
- `C` остальное

## Качественные анализы (`keywords.py`)

### `analyze_first_person_voice(text)`
Считает совпадения с FIRST_PERSON_MARKERS (`я`, `мой`, `мне`, `помогаю`, `научу`, `покажу`...). Плотность = совпадения / total_words. `has_strong_voice = count ≥5 AND density ≥1%`.

### `analyze_cta_markers(text)`
Ищет в тексте: "запись открыта", "стоимость", "тариф", "записаться", "оставить заявку", "регистрация" и т.д. `has_strong_cta = count ≥3`.

### `analyze_post_structure(posts)`
- `has_series`: ≥3 поста с маркерами `#N`, `часть N`, `выпуск N`, `день N`, `урок N`
- `has_rubrics`: ≥3 поста со словами `рубрика`, `серия`, `цикл`
- `has_consistent_format`: stddev длины постов < 50% от средней (только если ≥5 постов)

### `detect_autoposting(posts)`
Считает confidence (0–1) по сигналам:
- 60%+ постов в одном 30-мин окне → +0.4
- Маркеры автопостинга в тексте ("rss", "автоматическая публикация", "бот") → +0.5
- 50%+ коротких постов (<100 симв.) со ссылками → +0.3

`is_autopost = confidence ≥0.5`.

## Отбор для шортлиста и декомпозиции (`main.py`)

После сортировки всех каналов по `(analysis_priority, AQ score, expert_score, avg_post_reach, avg_comments)`:

**Eligible** = `is_expert_channel AND NOT false_positive_reason AND avg_post_reach ≥300`

- **selected_for_manual_analysis** = первые 20 eligible
- **selected_for_decomposition** = из них первые 5 у которых:
  - avg_comments > 3
  - avg_post_reach ≥ 700
  - days_since_last_post ≤ 14
  - channel_type не brand и не aggregator

## False-positive guards

`false_positive_reason` устанавливается если:
- В blacklist-маркерах есть совпадение (`shop_detected`, `brand_detected`, `aggregator_detected`, `news_detected`)
- Нет expert-маркеров и нет personal_brand → `no_author_detected`
- Качество ключей `weak` и канал не expert → `keyword_noise`
