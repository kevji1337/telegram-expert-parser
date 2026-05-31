"""
Работа с Telegram API
"""
import asyncio
from typing import Optional
from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, FloodWaitError, UsernameInvalidError, UsernameNotOccupiedError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel, Message
from config import SEARCH_LIMIT_PER_KEYWORD, MIN_PARTICIPANTS, FLOOD_WAIT_MAX_SEC, POSTS_TO_ANALYZE, FloodWaitTooLong


async def search_channels(client: TelegramClient, keyword: str, cache) -> list[Channel]:
    """Ищет каналы по ключевому слову (с SQLite кэшем)"""
    if len(keyword) < 3:
        return []

    # Проверяем кэш
    cached_ids = cache.get_search(keyword, ttl_days=3)
    if cached_ids is not None:
        print("     (из кэша)")
        channels: list[Channel] = []
        for cid in cached_ids:
            try:
                entity = await client.get_entity(cid)
                if isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                    channels.append(entity)
            except Exception:
                pass
        return channels

    try:
        result = await client(SearchRequest(q=keyword, limit=SEARCH_LIMIT_PER_KEYWORD))
    except FloodWaitError as e:
        if e.seconds > FLOOD_WAIT_MAX_SEC:
            raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
        await asyncio.sleep(e.seconds + 1)
        return []
    except Exception as e:
        print(f"     [!] ошибка поиска по '{keyword}': {e}")
        return []

    channels: list[Channel] = []
    for chat in result.chats:
        if not (isinstance(chat, Channel) and getattr(chat, "broadcast", False)):
            continue
        approx = getattr(chat, "participants_count", None) or 0
        if approx and approx < MIN_PARTICIPANTS:
            continue
        channels.append(chat)

    # Сохраняем в кэш
    cache.set_search(keyword, [ch.id for ch in channels])
    return channels


async def fetch_channel_full(client: TelegramClient, channel: Channel, cache) -> dict:
    """Получает полную информацию о канале (с SQLite кэшем)"""
    key = str(channel.id)

    # Проверяем кэш
    cached_data = cache.get_channel(key, ttl_days=7)
    if cached_data is not None:
        return cached_data

    try:
        full = await client(GetFullChannelRequest(channel))
        data = {
            "about": full.full_chat.about or "",
            "participants_count": full.full_chat.participants_count or 0,
            "pinned_msg_id": getattr(full.full_chat, "pinned_msg_id", None),
        }
        # Сохраняем в кэш
        cache.set_channel(key, data)
        return data
    except (ChannelPrivateError, UsernameInvalidError, UsernameNotOccupiedError):
        return {"about": "", "participants_count": 0, "pinned_msg_id": None}
    except FloodWaitError as e:
        if e.seconds > FLOOD_WAIT_MAX_SEC:
            raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
        await asyncio.sleep(e.seconds + 1)
        return {"about": "", "participants_count": 0, "pinned_msg_id": None}
    except Exception as e:
        print(f"     [!] full info error: {e}")
        return {"about": "", "participants_count": 0, "pinned_msg_id": None}


async def fetch_last_posts(client: TelegramClient, channel: Channel) -> list[Message]:
    """Получает последние посты канала"""
    try:
        return [m async for m in client.iter_messages(channel, limit=POSTS_TO_ANALYZE)]
    except FloodWaitError as e:
        if e.seconds > FLOOD_WAIT_MAX_SEC:
            raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
        await asyncio.sleep(e.seconds + 1)
        return []
    except Exception as e:
        print(f"     [!] posts error: {e}")
        return []


async def fetch_pinned_text(client: TelegramClient, channel: Channel, pinned_msg_id: Optional[int]) -> str:
    """Получает текст закрепленного сообщения"""
    if not pinned_msg_id:
        return ""
    try:
        m = await client.get_messages(channel, ids=pinned_msg_id)
        return (m.message or "").strip()
    except Exception:
        return ""


async def fetch_comments_from_posts(client: TelegramClient, channel: Channel, posts: list[Message], max_comments_per_post: int = 10) -> list[str]:
    """
    Парсит комментарии из постов канала

    Возвращает список текстов комментариев
    """
    all_comments = []

    for post in posts[:5]:  # берём только топ-5 постов
        if not post.replies or not post.replies.replies:
            continue

        try:
            comments = [c async for c in client.iter_messages(channel, reply_to=post.id, limit=max_comments_per_post)]
            for comment in comments:
                if comment.message:
                    all_comments.append(comment.message)
        except FloodWaitError as e:
            if e.seconds > FLOOD_WAIT_MAX_SEC:
                raise FloodWaitTooLong(f"FloodWait {e.seconds} сек") from e
            await asyncio.sleep(e.seconds + 1)
            break
        except Exception:
            continue

    return all_comments


async def get_channel_by_username(client: TelegramClient, username: str) -> Channel | None:
    """Получает канал по username"""
    try:
        entity = await client.get_entity(username)
        if isinstance(entity, Channel) and getattr(entity, "broadcast", False):
            return entity
    except Exception:
        pass
    return None
