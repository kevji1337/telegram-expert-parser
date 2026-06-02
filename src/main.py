"""
Главный модуль парсера Telegram каналов
"""
import asyncio
from datetime import datetime, timezone
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from config import (
    ACCOUNT_CONFIGS, TG_ACCOUNTS, KEYWORDS_FILE, OUTPUT_CSV, OUTPUT_SHORTLIST_CSV,
    OUTPUT_DECOMP_CSV, PROGRESS_FILE, CHECKPOINT_EVERY_N_CHANNELS,
    MIN_PARTICIPANTS, FloodWaitTooLong, FLOOD_WAIT_SWITCH_THRESHOLD, PARALLEL_MODE
)
from performance import split_keywords_across_accounts
from models import ChannelRow
from cache import load_niches, load_progress, save_progress
from sqlite_cache import SQLiteCache
from rate_limiter import AdaptiveRateLimiter
from telegram_client import (
    search_channels, fetch_channel_full, fetch_last_posts, fetch_pinned_text,
    fetch_comments_from_posts, get_channel_by_username
)
from recursive_search import RecursiveSearchQueue
from metrics import calc_metrics
from classification import classify_channel
from scoring import (
    evaluate, calc_monetization_score, calc_expert_score,
    calc_analysis_queue_score, calc_analysis_priority, calc_priority, build_top_signals
)
from keywords import (
    classify_keyword_quality, count_intent_keywords, extract_links, analyze_external_links, extract_mentions,
    analyze_first_person_voice, analyze_cta_markers, analyze_post_structure, detect_autoposting
)
from analytics import calc_growth_rate, calc_growth_rate_from_history, analyze_sentiment
from export import save_csv


async def build_row(client, channel, niche_key, niche_title, matched_keyword, channel_cache):
    username = channel.username or ""
    row = ChannelRow(
        title=channel.title or "",
        username=f"@{username}" if username else "",
        link=f"https://t.me/{username}" if username else "",
        niche_key=niche_key,
        niche_title=niche_title,
        matched_niches=niche_title,
        matched_keywords=matched_keyword,
        is_verified=bool(getattr(channel, "verified", False)),
        is_scam=bool(getattr(channel, "scam", False)),
        is_fake=bool(getattr(channel, "fake", False)),
    )

    full = await fetch_channel_full(client, channel, channel_cache)
    row.about = (full.get("about") or "").replace("\n", " ").strip()
    row.participants_count = int(full.get("participants_count") or 0)

    if row.participants_count and row.participants_count < MIN_PARTICIPANTS:
        return row

    posts = await fetch_last_posts(client, channel)
    pinned_text = await fetch_pinned_text(client, channel, full.get("pinned_msg_id"))
    row.pinned_text = pinned_text[:500].replace("\n", " ")
    row.pinned_links = "; ".join(extract_links(pinned_text))

    metrics = calc_metrics(posts, username)
    row.avg_views_last_posts = round(metrics["avg_views"], 1)
    row.avg_post_reach = int(metrics["median_views"])
    row.adv_post_reach_24h = int(metrics["median_views_24h"])
    row.avg_reactions = round(metrics["median_reactions"], 1)
    row.avg_comments = round(metrics["median_comments"], 1)
    row.posts_per_week = round(metrics["posts_per_week"], 2)

    if metrics["last_post_dt"]:
        row.last_post_date = metrics["last_post_dt"].strftime("%Y-%m-%d")
        row.days_since_last_post = (datetime.now(tz=timezone.utc) - metrics["last_post_dt"]).days
    else:
        row.days_since_last_post = 9999

    row.last_post_links = "; ".join(metrics["links"])

    if row.participants_count > 0:
        row.view_to_subs_ratio = round(row.avg_views_last_posts / row.participants_count, 4)
        row.err_percent = round(row.avg_views_last_posts / row.participants_count * 100, 2)
        if row.adv_post_reach_24h:
            row.err24_percent = round(row.adv_post_reach_24h / row.participants_count * 100, 2)

    if row.avg_views_last_posts > 0 and row.avg_reactions > 0:
        row.engagement_percent = round(row.avg_reactions / row.avg_views_last_posts * 100, 2)

    cls = classify_channel(row.title, row.about, posts, pinned_text=row.pinned_text)
    row.channel_type = cls["channel_type"]
    row.is_expert_channel = cls["is_expert_channel"]
    row.author_name = cls["author_name"]
    row.author_contact = cls["author_contact"]
    row.has_external_links = cls["has_external_links"]
    row.has_consulting_offer = cls["has_consulting_offer"]
    row.has_course_offer = cls["has_course_offer"]
    row.has_testimonials = cls["has_testimonials"]
    row.has_personal_brand = cls["has_personal_brand"]

    # Анализ внешних ссылок
    all_links = extract_links(row.about) + extract_links(row.pinned_text)
    link_analysis = analyze_external_links(all_links)
    row.has_youtube = link_analysis["has_youtube"]
    row.has_instagram = link_analysis["has_instagram"]
    row.has_getcourse = link_analysis["has_getcourse"]
    row.has_taplink = link_analysis["has_taplink"]
    row.has_calendly = link_analysis["has_calendly"]
    row.has_forms = link_analysis["has_forms"]
    row.has_payment = link_analysis["has_payment"]
    row.has_booking = link_analysis["has_booking"]

    # Сохраняем все внешние ссылки (не t.me)
    external_only = [link for link in all_links if "t.me" not in link.lower()]
    row.external_links = "; ".join(external_only[:10])  # макс 10 ссылок

    # Парсинг упоминаний каналов из about + pinned + последние 10 постов
    all_text = row.about + "\n" + row.pinned_text
    for post in posts[:10]:
        if post.message:
            all_text += "\n" + post.message
    mentions = extract_mentions(all_text)
    row.mentioned_channels = ", ".join(mentions[:20])  # макс 20 упоминаний

    # НОВОЕ: Анализ "1-го лица"
    first_person = analyze_first_person_voice(all_text)
    row.first_person_count = first_person["first_person_count"]
    row.first_person_density = first_person["first_person_density"]
    row.has_strong_voice = first_person["has_strong_voice"]

    # НОВОЕ: Анализ CTA
    cta = analyze_cta_markers(all_text)
    row.cta_count = cta["cta_count"]
    row.has_strong_cta = cta["has_strong_cta"]

    # НОВОЕ: Анализ структуры постов
    structure = analyze_post_structure(posts)
    row.has_series = structure["has_series"]
    row.has_rubrics = structure["has_rubrics"]
    row.avg_post_length = structure["avg_post_length"]
    row.has_consistent_format = structure["has_consistent_format"]

    # НОВОЕ: Детект автопостинга
    autopost = detect_autoposting(posts)
    row.is_autopost = autopost["is_autopost"]
    row.autopost_confidence = autopost["autopost_confidence"]

    # НОВОЕ: Топ-пост анализ
    if posts:
        top_post = max(posts, key=lambda p: p.views if p.views else 0)
        row.top_post_views = top_post.views if top_post.views else 0
        if username and top_post.id:
            row.top_post_link = f"https://t.me/{username}/{top_post.id}"

    # НОВОЕ: Sentiment analysis (постов + about + pinned)
    sentiment_texts = [row.about, row.pinned_text]
    for post in posts[:20]:
        if post.message:
            sentiment_texts.append(post.message)
    row.sentiment_score = analyze_sentiment(sentiment_texts)

    if metrics["median_comments"] > 0:
        comments = await fetch_comments_from_posts(client, channel, posts)
        row.comment_sentiment_score = analyze_sentiment(comments)

    # Growth rate по истории замеров (subs_history)
    if row.participants_count > 0:
        channel_cache.record_subs(str(channel.id), row.participants_count)
        history = channel_cache.get_subs_history(str(channel.id))
        row.growth_rate = calc_growth_rate_from_history(history)

    row.keyword_match_quality = classify_keyword_quality(row.matched_keywords)
    intent_kw_count = count_intent_keywords(row.matched_keywords)

    fp = ""
    if row.is_scam:
        fp = "scam_flag"
    elif row.is_fake:
        fp = "fake_flag"
    elif cls["blacklist_hit"]:
        fp_map = {"shop": "shop_detected", "brand": "brand_detected", "aggregator": "aggregator_detected", "news": "news_detected"}
        fp = fp_map.get(cls["blacklist_top"], "brand_detected")
    elif cls["expert_marker_count"] == 0 and row.has_personal_brand != "True":
        fp = "no_author_detected"
    elif row.keyword_match_quality == "weak" and not row.is_expert_channel:
        fp = "keyword_noise"
    row.false_positive_reason = fp

    row.is_suitable, row.reason = evaluate(row)
    row.monetization_score = calc_monetization_score(row)
    row.priority_status = calc_priority(row)
    row.expert_score = calc_expert_score(row, intent_hits=int(cls.get("intent_hits") or 0), intent_keyword_count=intent_kw_count)
    row.analysis_queue_score = calc_analysis_queue_score(row)
    row.analysis_priority = calc_analysis_priority(row.analysis_queue_score)
    row.top_signals = build_top_signals(row)
    return row


async def process_account_keywords(
    account_name: str,
    keyword_triples: list[tuple[str, str, str]],
    seen: dict,
    seen_lock: asyncio.Lock,
    cache,
    state: dict,
):
    """
    Параллельный worker: один аккаунт обрабатывает свой набор ключей.

    keyword_triples: список (niche_key, niche_title, keyword)
    state: общий словарь со счётчиком processed_count и pending-чекпоинтами
    """
    cfg = ACCOUNT_CONFIGS[account_name]
    print(f"[+] [{account_name}] Подключаюсь (session={cfg['session']}), ключей: {len(keyword_triples)}")

    rate_limiter = AdaptiveRateLimiter(initial_delay=0.35, min_delay=0.1, max_delay=5.0)
    client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
    await client.start()

    try:
        for niche_key, niche_title, kw in keyword_triples:
            print(f"  [{account_name}] -> '{kw}' ({niche_title})")
            await rate_limiter.wait()

            try:
                found = await search_channels(client, kw, cache)
                rate_limiter.on_success()
                print(f"     [{account_name}] найдено: {len(found)}")
            except FloodWaitError as e:
                rate_limiter.on_flood_wait(e.seconds)
                if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                    raise FloodWaitTooLong(f"FloodWait {e.seconds} сек на {account_name}") from e
                print(f"     [{account_name}] FloodWait {e.seconds}s")
                await asyncio.sleep(e.seconds + 1)
                continue
            except Exception as e:
                rate_limiter.on_error()
                print(f"     [{account_name}] ошибка поиска: {e}")
                continue

            for ch in found:
                async with seen_lock:
                    if ch.id in seen:
                        existing = seen[ch.id]
                        kws = [k.strip() for k in existing.matched_keywords.split(",") if k.strip()]
                        if kw not in kws:
                            kws.append(kw)
                            existing.matched_keywords = ", ".join(kws)
                        nichs = [n.strip() for n in existing.matched_niches.split(",") if n.strip()]
                        if niche_title not in nichs:
                            nichs.append(niche_title)
                            existing.matched_niches = ", ".join(nichs)
                        existing.keyword_match_quality = classify_keyword_quality(existing.matched_keywords)
                        if existing.false_positive_reason == "keyword_noise" and existing.keyword_match_quality in ("strong", "medium"):
                            existing.false_positive_reason = ""
                        continue
                    # резервируем место чтобы другие worker'ы не дублировали
                    seen[ch.id] = None

                await rate_limiter.wait()

                try:
                    row = await build_row(client, ch, niche_key, niche_title, kw, cache)
                    rate_limiter.on_success()
                except FloodWaitError as e:
                    rate_limiter.on_flood_wait(e.seconds)
                    async with seen_lock:
                        seen.pop(ch.id, None)
                    if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                        raise FloodWaitTooLong(f"FloodWait {e.seconds} сек на {account_name}") from e
                    print(f"     [{account_name}] FloodWait {e.seconds}s")
                    await asyncio.sleep(e.seconds + 1)
                    continue
                except Exception as e:
                    rate_limiter.on_error()
                    async with seen_lock:
                        seen.pop(ch.id, None)
                    print(f"     [{account_name}] ошибка канала: {e}")
                    continue

                async with seen_lock:
                    seen[ch.id] = row
                    state["processed"] += 1
                    processed = state["processed"]

                mark = "E" if row.is_expert_channel else ("+" if row.is_suitable else "-")
                fp = f" FP={row.false_positive_reason}" if row.false_positive_reason else ""
                print(
                    f"     [{account_name}] {mark} [{row.priority_status} exp={row.expert_score:3d} aq={row.analysis_queue_score:3d} "
                    f"type={row.channel_type:10s}] {row.username or row.title} ({row.participants_count} подп.){fp}"
                )

                if processed % CHECKPOINT_EVERY_N_CHANNELS == 0:
                    async with seen_lock:
                        rows_tmp = [r for r in seen.values() if r is not None]
                    save_csv(rows_tmp, OUTPUT_CSV)
                    print(f"     [✓] Чекпоинт ({account_name}): {len(rows_tmp)} каналов")

            await asyncio.sleep(2.0)

    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def run_parallel(niches, cache, seen: dict):
    """Параллельный режим: ключи разбиваются между аккаунтами и обрабатываются одновременно"""
    triples: list[tuple[str, str, str]] = []
    for niche_key, niche_title, keywords in niches:
        for kw in keywords:
            triples.append((niche_key, niche_title, kw))

    buckets = split_keywords_across_accounts(triples, len(TG_ACCOUNTS))
    print(f"[+] Параллельный режим: {len(triples)} ключей разбито на {len(TG_ACCOUNTS)} аккаунтов")
    for acc, bucket in zip(TG_ACCOUNTS, buckets):
        print(f"     {acc}: {len(bucket)} ключей")

    seen_lock = asyncio.Lock()
    state = {"processed": 0}

    tasks = [
        process_account_keywords(acc, bucket, seen, seen_lock, cache, state)
        for acc, bucket in zip(TG_ACCOUNTS, buckets) if bucket
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for acc, result in zip(TG_ACCOUNTS, results):
        if isinstance(result, Exception):
            print(f"[!] Аккаунт {acc} упал: {result}")

    # очищаем None-зарезервированные слоты
    for k in list(seen.keys()):
        if seen[k] is None:
            seen.pop(k, None)

    print(f"[+] Параллельный парсинг завершён. Обработано: {state['processed']}")


async def _run_recursive_search(seen: dict, cache):
    """Запускает рекурсивный поиск по упоминаниям через первый доступный аккаунт"""
    if not seen:
        return
    print(f"\n=== Запуск рекурсивного поиска по упоминаниям ===")
    recursive_queue = RecursiveSearchQueue(max_depth=1, max_channels=100)
    for ch_id, row in seen.items():
        if row is None:
            continue
        if row.is_expert_channel and row.mentioned_channels:
            mentions = [m.strip() for m in row.mentioned_channels.split(",") if m.strip()]
            source_username = row.username.lstrip("@") if row.username else str(ch_id)
            recursive_queue.add_mentions(source_username, mentions, current_depth=0)
    print(f"     Очередь рекурсивного поиска: {len(recursive_queue)} каналов")
    if recursive_queue.is_empty():
        return

    account_name = TG_ACCOUNTS[0]
    cfg = ACCOUNT_CONFIGS[account_name]
    rate_limiter = AdaptiveRateLimiter(initial_delay=0.35, min_delay=0.1, max_delay=5.0)
    client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
    await client.start()

    recursive_processed = 0
    try:
        while not recursive_queue.is_empty() and recursive_processed < 50:
            item = recursive_queue.get_next()
            if not item:
                break
            username, depth, source = item
            await rate_limiter.wait()
            try:
                ch = await get_channel_by_username(client, username)
                if not ch or ch.id in seen:
                    continue
                row = await build_row(client, ch, "recursive", "рекурсивный поиск", f"mention:{source}", cache)
                rate_limiter.on_success()
                seen[ch.id] = row
                recursive_processed += 1
                mark = "E" if row.is_expert_channel else ("+" if row.is_suitable else "-")
                print(f"     [REC d={depth}] {mark} {row.username or row.title} ({row.participants_count} подп.) <- {source}")
            except FloodWaitError as e:
                rate_limiter.on_flood_wait(e.seconds)
                if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                    print(f"     [REC] FloodWait слишком долгий, прерываю рекурсивный поиск")
                    break
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                rate_limiter.on_error()
                print(f"     [REC] ошибка для {username}: {e}")
                continue

        networks = recursive_queue.detect_cross_promo_networks()
        if networks:
            print(f"\n     Обнаружено кросс-промо сетей: {len(networks)}")
            for i, net in enumerate(networks[:5], 1):
                print(f"       Сеть #{i}: {', '.join(list(net)[:5])}")
    finally:
        await client.disconnect()


def _finalize_and_save(seen: dict):
    """Сортирует каналы, выделяет шортлист/декомпозицию, сохраняет 3 CSV"""
    rows = [r for r in seen.values() if r is not None]

    apq_order = {"ANALYZE": 0, "RESERVE": 1, "IGNORE": 2}
    rows.sort(key=lambda r: (
        apq_order.get(r.analysis_priority, 2),
        -r.analysis_queue_score,
        -r.expert_score,
        -r.avg_post_reach,
        -r.avg_comments,
    ))

    eligible = [r for r in rows if r.is_expert_channel and not r.false_positive_reason and r.avg_post_reach >= 300]
    for idx, r in enumerate(eligible, start=1):
        r.final_rank = idx
    for r in eligible[:20]:
        r.selected_for_manual_analysis = True

    decomp_candidates = [
        r for r in eligible[:20]
        if r.avg_comments > 3
        and r.avg_post_reach >= 700
        and r.days_since_last_post <= 14
        and r.channel_type not in ("brand", "aggregator")
    ]
    for r in decomp_candidates[:5]:
        r.selected_for_decomposition = True

    save_csv(rows, OUTPUT_CSV)
    save_csv([r for r in rows if r.selected_for_manual_analysis], OUTPUT_SHORTLIST_CSV)
    save_csv([r for r in rows if r.selected_for_decomposition], OUTPUT_DECOMP_CSV)

    buckets = {"ANALYZE": 0, "RESERVE": 0, "IGNORE": 0}
    for r in rows:
        buckets[r.analysis_priority] = buckets.get(r.analysis_priority, 0) + 1

    manual_count = sum(1 for r in rows if r.selected_for_manual_analysis)
    decomp_count = sum(1 for r in rows if r.selected_for_decomposition)

    print("\n=== Очередь ручного анализа ===")
    print(f"ANALYZE:  {buckets['ANALYZE']} каналов")
    print(f"RESERVE:  {buckets['RESERVE']} каналов")
    print(f"IGNORE:   {buckets['IGNORE']} каналов")
    print("\n=== Отобрано для работы ===")
    print(f"Ручной анализ (selected_for_manual_analysis): {manual_count} каналов")
    print(f"Декомпозиция (selected_for_decomposition):     {decomp_count} каналов")


async def main():
    """Основной цикл парсера"""
    niches = load_niches(KEYWORDS_FILE)
    print(f"[+] Загружено ниш из {KEYWORDS_FILE}: {len(niches)}")

    # SQLite кэш вместо JSON
    cache = SQLiteCache("cache.db")
    print(f"[+] Используется SQLite кэш: cache.db")

    progress = load_progress(PROGRESS_FILE)
    start_niche_idx = int(progress.get("niche_idx") or 0)
    start_kw_idx = int(progress.get("kw_idx") or 0)

    seen = {}
    processed_count = 0
    account_idx = 0

    if PARALLEL_MODE:
        try:
            await run_parallel(niches, cache, seen)
        except Exception as e:
            print(f"[!] Параллельный режим упал: {e}. Сохраняю что есть.")

        await _run_recursive_search(seen, cache)
        _finalize_and_save(seen)
        return

    while account_idx < len(TG_ACCOUNTS):
        account_name = TG_ACCOUNTS[account_idx]
        cfg = ACCOUNT_CONFIGS[account_name]
        print(f"\n[+] Подключаюсь к аккаунту: {account_name} (session={cfg['session']})")

        # Адаптивный rate limiter для каждого аккаунта
        rate_limiter = AdaptiveRateLimiter(initial_delay=0.35, min_delay=0.1, max_delay=5.0)

        client = TelegramClient(cfg["session"], cfg["api_id"], cfg["api_hash"])
        await client.start()

        try:
            for niche_idx, (niche_key, niche_title, keywords) in enumerate(niches):
                if niche_idx < start_niche_idx:
                    continue
                print(f"\n=== Ниша: {niche_title} ({niche_key}) ===")

                kw_start = start_kw_idx if niche_idx == start_niche_idx else 0

                for kw_idx, kw in enumerate(keywords):
                    if kw_idx < kw_start:
                        continue

                    save_progress({"niche_idx": niche_idx, "kw_idx": kw_idx}, PROGRESS_FILE)

                    print(f"  -> поиск по '{kw}'")
                    await rate_limiter.wait()

                    try:
                        found = await search_channels(client, kw, cache)
                        rate_limiter.on_success()
                        print(f"     найдено каналов: {len(found)}")
                    except FloodWaitError as e:
                        rate_limiter.on_flood_wait(e.seconds)
                        if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                            raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
                        print(f"     [!] FloodWait {e.seconds}s, ждём...")
                        await asyncio.sleep(e.seconds + 1)
                        continue
                    except Exception as e:
                        rate_limiter.on_error()
                        print(f"     [!] ошибка: {e}")
                        continue

                    for ch in found:
                        if ch.id in seen:
                            existing = seen[ch.id]
                            kws = [k.strip() for k in existing.matched_keywords.split(",") if k.strip()]
                            if kw not in kws:
                                kws.append(kw)
                                existing.matched_keywords = ", ".join(kws)
                            nichs = [n.strip() for n in existing.matched_niches.split(",") if n.strip()]
                            if niche_title not in nichs:
                                nichs.append(niche_title)
                                existing.matched_niches = ", ".join(nichs)
                            existing.keyword_match_quality = classify_keyword_quality(existing.matched_keywords)
                            if existing.false_positive_reason == "keyword_noise" and existing.keyword_match_quality in ("strong", "medium"):
                                existing.false_positive_reason = ""
                            continue

                        await rate_limiter.wait()

                        try:
                            row = await build_row(client, ch, niche_key, niche_title, kw, cache)
                            rate_limiter.on_success()
                        except FloodWaitError as e:
                            rate_limiter.on_flood_wait(e.seconds)
                            if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                                raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
                            print(f"     [!] FloodWait {e.seconds}s, ждём...")
                            await asyncio.sleep(e.seconds + 1)
                            continue
                        except Exception as e:
                            rate_limiter.on_error()
                            print(f"     [!] ошибка обработки канала: {e}")
                            continue

                        seen[ch.id] = row
                        processed_count += 1

                        mark = "E" if row.is_expert_channel else ("+" if row.is_suitable else "-")
                        fp = f" FP={row.false_positive_reason}" if row.false_positive_reason else ""
                        delay_info = f" [delay={rate_limiter.get_current_delay():.2f}s]"
                        print(
                            f"     {mark} [{row.priority_status} exp={row.expert_score:3d} aq={row.analysis_queue_score:3d} "
                            f"type={row.channel_type:10s} kw={row.keyword_match_quality:6s}] "
                            f"{row.username or row.title} ({row.participants_count} подп.){fp}{delay_info}"
                        )

                        if processed_count % CHECKPOINT_EVERY_N_CHANNELS == 0:
                            rows_tmp = list(seen.values())
                            save_csv(rows_tmp, OUTPUT_CSV)
                            print(f"     [✓] Чекпоинт: сохранено {len(rows_tmp)} каналов")

                    await asyncio.sleep(2.0)

            # === РЕКУРСИВНЫЙ ПОИСК ПО УПОМИНАНИЯМ ===
            print(f"\n=== Запуск рекурсивного поиска по упоминаниям ===")
            recursive_queue = RecursiveSearchQueue(max_depth=1, max_channels=100)

            # Собираем упоминания из найденных экспертных каналов
            for ch_id, row in seen.items():
                if row.is_expert_channel and row.mentioned_channels:
                    mentions = [m.strip() for m in row.mentioned_channels.split(",") if m.strip()]
                    source_username = row.username.lstrip("@") if row.username else str(ch_id)
                    recursive_queue.add_mentions(source_username, mentions, current_depth=0)

            print(f"     Очередь рекурсивного поиска: {len(recursive_queue)} каналов")

            # Обрабатываем очередь
            recursive_processed = 0
            while not recursive_queue.is_empty() and recursive_processed < 50:
                item = recursive_queue.get_next()
                if not item:
                    break
                username, depth, source = item

                await rate_limiter.wait()

                try:
                    ch = await get_channel_by_username(client, username)
                    if not ch or ch.id in seen:
                        continue

                    row = await build_row(client, ch, "recursive", "рекурсивный поиск", f"mention:{source}", cache)
                    rate_limiter.on_success()
                    seen[ch.id] = row
                    recursive_processed += 1

                    mark = "E" if row.is_expert_channel else ("+" if row.is_suitable else "-")
                    print(f"     [REC d={depth}] {mark} {row.username or row.title} ({row.participants_count} подп.) <- {source}")
                except FloodWaitError as e:
                    rate_limiter.on_flood_wait(e.seconds)
                    if e.seconds > FLOOD_WAIT_SWITCH_THRESHOLD:
                        raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
                    await asyncio.sleep(e.seconds + 1)
                except Exception as e:
                    rate_limiter.on_error()
                    print(f"     [REC] ошибка для {username}: {e}")
                    continue

            # Детект кросс-промо сетей
            networks = recursive_queue.detect_cross_promo_networks()
            if networks:
                print(f"\n     Обнаружено кросс-промо сетей: {len(networks)}")
                for i, net in enumerate(networks[:5], 1):
                    print(f"       Сеть #{i}: {', '.join(list(net)[:5])}")

            await client.disconnect()
            break

        except FloodWaitTooLong as e:
            print(f"\n[!] Аккаунт {account_name} словил FloodWait ({e}).")
            await client.disconnect()

            rows_tmp = list(seen.values())
            if rows_tmp:
                save_csv(rows_tmp, OUTPUT_CSV)

            account_idx += 1
            if account_idx < len(TG_ACCOUNTS):
                print("[+] Переключаюсь на следующий аккаунт...")
                continue
            print(f"[!] Все {len(TG_ACCOUNTS)} аккаунтов заблокированы. Выхожу.")
            break

        except KeyboardInterrupt:
            print("\n[!] Прервано пользователем (Ctrl+C). Сохраняем прогресс.")
            await client.disconnect()
            break

    rows = list(seen.values())

    apq_order = {"ANALYZE": 0, "RESERVE": 1, "IGNORE": 2}
    rows.sort(key=lambda r: (
        apq_order.get(r.analysis_priority, 2),
        -r.analysis_queue_score,
        -r.expert_score,
        -r.avg_post_reach,
        -r.avg_comments,
    ))

    eligible = [r for r in rows if r.is_expert_channel and not r.false_positive_reason and r.avg_post_reach >= 300]
    for idx, r in enumerate(eligible, start=1):
        r.final_rank = idx

    for r in eligible[:20]:
        r.selected_for_manual_analysis = True

    decomp_candidates = [
        r for r in eligible[:20]
        if r.avg_comments > 3
        and r.avg_post_reach >= 700
        and r.days_since_last_post <= 14
        and r.channel_type not in ("brand", "aggregator")
    ]
    for r in decomp_candidates[:5]:
        r.selected_for_decomposition = True

    save_csv(rows, OUTPUT_CSV)
    save_csv([r for r in rows if r.selected_for_manual_analysis], OUTPUT_SHORTLIST_CSV)
    save_csv([r for r in rows if r.selected_for_decomposition], OUTPUT_DECOMP_CSV)

    buckets = {"ANALYZE": 0, "RESERVE": 0, "IGNORE": 0}
    for r in rows:
        buckets[r.analysis_priority] = buckets.get(r.analysis_priority, 0) + 1

    manual_count = sum(1 for r in rows if r.selected_for_manual_analysis)
    decomp_count = sum(1 for r in rows if r.selected_for_decomposition)

    print("\n=== Очередь ручного анализа ===")
    print(f"ANALYZE:  {buckets['ANALYZE']} каналов")
    print(f"RESERVE:  {buckets['RESERVE']} каналов")
    print(f"IGNORE:   {buckets['IGNORE']} каналов")
    print("\n=== Отобрано для работы ===")
    print(f"Ручной анализ (selected_for_manual_analysis): {manual_count} каналов")
    print(f"Декомпозиция (selected_for_decomposition):     {decomp_count} каналов")


if __name__ == "__main__":
    asyncio.run(main())
