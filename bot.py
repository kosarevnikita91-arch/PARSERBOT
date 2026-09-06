import aiogram
import os
import re
import asyncio
import sqlite3
from typing import List
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()



from collections import Counter
from datetime import datetime, timedelta, timezone


api_id=24078627
api_hash="4bfeafd8075403696854929d52fc5b7b"
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import (
    GetParticipantRequest,
    GetFullChannelRequest,
)
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.tl.types import (
    ChannelParticipantAdmin,
    ChannelParticipantCreator,
    DialogFilter,
    UserStatusOnline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
)






client = TelegramClient(
    "session_name",
    api_id,
    api_hash
)



load_dotenv()




api_id = 24078627
api_hash = "4bfeafd8075403696854929d52fc5b7b"

client = TelegramClient("my_user_session", api_id, api_hash)

client.start(
    phone="+79173641366",
    password=lambda: input("Введите пароль 2FA: ")
)

print("Аккаунт подключён")
client.run_until_disconnected()






import os
from pathlib import Path
from telethon import TelegramClient



session_dir = Path(__file__).parent / "sessions"
session_dir.mkdir(exist_ok=True)


client = TelegramClient(


 proxy={
        "proxy_type": "socks5",
        "addr": "127.0.0.1",
        "port": 9150 }
)

client.start()
print("Подключение выполнено")
client.run_until_disconnected()



load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID"))

RECIPIENT_IDS = [
    OWNER_ID,
    6977495013,
    2117149396,
    8190307950,
    7066297390,
    8177297993,
]

AUTHORIZED_USERS = set(RECIPIENT_IDS)

BATCH_SIZE = 50
TARGET_USERS = 300
REQUIRED_USERS = TARGET_USERS
DAYS_TO_PARSE = 2
PARSING_HOURS = 6
STATUS_INTERVAL_SECONDS = 60 * 60

parsing_task = None
parsing_started_at = None
parsing_deadline = None

distribution_lock = asyncio.Lock()
parsing_lock = asyncio.Lock()

telegram_client = TelegramClient(
    "telegram_profile",
    API_ID,
    API_HASH,
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

db = sqlite3.connect(
    "users.db",
    check_same_thread=False,
)
db.row_factory = sqlite3.Row


def init_db():
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            deleted INTEGER DEFAULT 0,
            premium INTEGER DEFAULT 0,
            last_seen TEXT DEFAULT 'hidden',
            is_admin INTEGER DEFAULT 0,
            possible_bot INTEGER DEFAULT 0,
            bot_reasons TEXT,
            user_rating INTEGER DEFAULT 0,
            source_chat_id INTEGER,
            source_chat_title TEXT,
            source_message_id INTEGER,
            source_message_link TEXT,
            comment_count INTEGER DEFAULT 0,
            assigned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS excluded_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            source_link TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS processed_posts (
            chat_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (chat_id, post_id)
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS channel_ratings (
            chat_id INTEGER PRIMARY KEY,
            title TEXT,
            subscribers_score INTEGER DEFAULT 0,
            activity_score INTEGER DEFAULT 0,
            comments_score INTEGER DEFAULT 0,
            views_score INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for column in ("user_rating",):
        try:
            db.execute(
                f"ALTER TABLE users ADD COLUMN {column} INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError:
            pass

    db.commit()


def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS


def get_unassigned_count() -> int:
    row = db.execute("""
        SELECT COUNT(*) AS total
        FROM users
        WHERE assigned = 0
          AND NOT EXISTS (
              SELECT 1
              FROM excluded_users
              WHERE excluded_users.telegram_id = users.telegram_id
          )
    """).fetchone()
    return row["total"]


def score_marker(score: int) -> str:
    if score >= 80:
        return "🟢"
    if score >= 35:
        return "🟡"
    return "🔴"


def rating_text(score: int) -> str:
    return f"{score}/100 {score_marker(score)}"


async def notify_authorized_users(text: str):
    for user_id in RECIPIENT_IDS:
        try:
            await bot.send_message(user_id, text)
            await asyncio.sleep(0.3)
        except Exception as error:
            print(f"Ошибка отправки уведомления {user_id}: {error}")


def get_remaining_time_text() -> str:
    if parsing_deadline is None:
        return "Автоматический парсинг не запущен."

    remaining = parsing_deadline - datetime.now(timezone.utc)

    if remaining.total_seconds() <= 0:
        return "Время парсинга истекло."

    total_seconds = int(remaining.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"Осталось: {hours} ч. {minutes} мин. {seconds} сек."


def get_last_seen_category(user):
    status = getattr(user, "status", None)

    if status is None:
        return "hidden"
    if isinstance(status, UserStatusOnline):
        return "online"
    if isinstance(status, UserStatusRecently):
        return "recently"
    if isinstance(status, UserStatusLastWeek):
        return "last_week"
    if isinstance(status, UserStatusLastMonth):
        return "last_month"

    return "offline"

    def detect_possible_bot(user, comment_texts: list):
        reasons = []

        username = (
                getattr(user, "username", None) or ""
        ).lower()

        first_name = (
                getattr(user, "first_name", None) or ""
        ).strip()

        if not first_name:
            reasons.append("нет имени")

        bot_words = (
            "bot",
            "robot",
            "auto",
            "support",
            "service",
            "admin",
        )

        if username and any(
                word in username
                for word in bot_words
        ):
            reasons.append(
                "подозрительный username"
            )

        normalized_texts = [
            re.sub(
                r"\s+",
                " ",
                text.lower(),
            ).strip()
            for text in comment_texts
            if text.strip()
        ]

        if len(normalized_texts) >= 3:
            repeated = Counter(
                normalized_texts
            ).most_common(1)[0][1]

            if repeated >= 2:
                reasons.append(
                    "повторяющиеся комментарии"
                )

        if getattr(user, "deleted", False):
            reasons.append(
                "удалённый аккаунт"
            )

        return bool(reasons), "; ".join(reasons)


def calculate_user_rating(user, comment_count: int, is_admin: bool) -> int:
    score = 0

    if not getattr(user, "deleted", False):
        score += 20

    if getattr(user, "first_name", None):
        score += 10

    if getattr(user, "last_name", None):
        score += 5

    if getattr(user, "username", None):
        score += 10

    if getattr(user, "premium", False):
        score += 15

    if is_admin:
        score += 10

    score += min(comment_count * 5, 20)

    status = get_last_seen_category(user)
    if status == "online":
        score += 10
    elif status == "recently":
        score += 7
    elif status == "last_week":
        score += 4

    return min(score, 100)


async def check_is_admin(chat, user_id: int) -> bool:
    try:
        result = await telegram_client(
            GetParticipantRequest(
                channel=chat,
                participant=user_id,
            )
        )
        client = TelegramClient(
            "session",
            api_id,
            api_hash
        )
        from telethon import TelegramClient
        from telethon.network.connection import ConnectionTcpFull

        client = TelegramClient(
            "session",
            api_id,
            api_hash,
            connection=ConnectionTcpFull,
            use_ipv6=False,
            timeout=30,
            connection_retries=5
        )

        return isinstance(
            result.participant,
            (
                ChannelParticipantAdmin,
                ChannelParticipantCreator,
            ),
        )
    except Exception:
        return False


def get_public_chat_name(entity):
    return (
        getattr(entity, "title", None)
        or getattr(entity, "username", None)
        or str(getattr(entity, "id", "unknown"))
    )


async def make_message_link(entity, message_id: int):
    try:
        return await telegram_client.get_message_link(
            entity,
            message_id,
        )
    except Exception:
        return None


def make_user_link(row):
    username = row["username"]
    message_link = row["source_message_link"]
    telegram_id = row["telegram_id"]

    if username:
        return f"https://t.me/{username}"
    if message_link:
        return message_link

    return f"tg://user?id={telegram_id}"


def make_result_line(row):
    link = make_user_link(row)
    labels = [
        f"рейтинг: {rating_text(row['user_rating'] or 0)}"
    ]

    if row["deleted"]:
        labels.append("удалённый")

    if row["premium"]:
        labels.append("Premium")

    if row["is_admin"]:
        labels.append("администратор")

    if row["possible_bot"]:
        labels.append(
            "возможный бот: "
            + (
                row["bot_reasons"]
                or "подозрительные признаки"
            )
        )

    return f"{link} — {', '.join(labels)}"

    def extract_user_links(text: str) -> list:
        pattern = (
            r"(?:https?://)?"
            r"t\.me/[A-Za-z0-9_]{4,}"
            r"|@[A-Za-z0-9_]{4,}"
        )

        return re.findall(pattern, text or "")

    return result


async def resolve_user_from_link(link: str):
    try:
        username = link.rstrip("/").split("/")[-1]
        if username.startswith("@"):
            username = username[1:]

        if username.isdigit():
            return await telegram_client.get_entity(int(username))

        return await telegram_client.get_entity(username)
    except Exception:
        return None

    async def add_excluded_links(links: list) -> tuple:
       added = 0
    duplicates = 0

    for link in links[:100]:
        user = await resolve_user_from_link(link)
        telegram_id = getattr(user, "id", None) if user else None
        username = getattr(user, "username", None) if user else None

        existing = db.execute("""
            SELECT 1
            FROM excluded_users
            WHERE source_link = ?
               OR (
                   telegram_id IS NOT NULL
                   AND telegram_id = ?
               )
        """, (link, telegram_id)).fetchone()

        if existing:
            duplicates += 1
            continue

        try:
            db.execute("""
                INSERT INTO excluded_users (
                    telegram_id,
                    username,
                    source_link
                )
                VALUES (?, ?, ?)
            """, (telegram_id, username, link))
            added += 1
        except sqlite3.IntegrityError:
            duplicates += 1

    db.commit()
    return added, duplicates


async def resolve_source(source_text: str):
    source_text = source_text.strip()

    if not source_text:
        raise ValueError("Источник не указан.")

    if source_text.lstrip("-").isdigit():
        return await telegram_client.get_entity(int(source_text))

    original_source = source_text

    for prefix in (
        "https://t.me/",
        "http://t.me/",
        "https://telegram.me/",
        "http://telegram.me/",
        "telegram.me/",
    ):
        source_text = source_text.replace(prefix, "")

    if source_text.startswith("+"):
        return await telegram_client.get_entity(
            "https://t.me/" + source_text
        )

    username = source_text.split("/")[0].strip().lstrip("@")

    try:
        return await telegram_client.get_entity(username)
    except Exception:
        pass

    async for dialog in telegram_client.iter_dialogs():
        dialog_name = (dialog.name or "").strip().lower()

        if dialog_name == original_source.lower():
            return dialog.entity

    matches = []

    async for dialog in telegram_client.iter_dialogs():
        dialog_name = (dialog.name or "").strip().lower()

        if original_source.lower() in dialog_name:
            matches.append(dialog)

    if len(matches) == 1:
        return matches[0].entity

    if len(matches) > 1:
        names = "\n".join(
            f"- {item.name} | ID: {item.id}"
            for item in matches[:10]
        )
        raise ValueError(
            "Найдено несколько похожих источников:\n\n" + names
        )

    raise ValueError("Группа или канал не найдены.")


async def get_stay_folder_id():
    result = await telegram_client(
        GetDialogFiltersRequest()
    )

    for folder in result.filters:
        if isinstance(folder, DialogFilter):
            if str(folder.title).lower() == "stay":
                return folder.id

    return None


async def get_channels_from_stay():
    stay_folder_id = await get_stay_folder_id()

    if stay_folder_id is None:
        raise ValueError("Папка Stay не найдена.")

    channels = []

    async for dialog in telegram_client.iter_dialogs():
        if dialog.folder_id != stay_folder_id:
            continue

        entity = dialog.entity

        if getattr(entity, "broadcast", False):
            channels.append(entity)

    return channels


async def has_recent_posts(entity, days=2):
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async for post in telegram_client.iter_messages(entity, limit=1):
        if not post.date:
            return False

        post_date = post.date

        if post_date.tzinfo is None:
            post_date = post_date.replace(tzinfo=timezone.utc)

        return post_date >= since

    return False


async def get_discussion_chat(channel):
    try:
        full = await telegram_client(
            GetFullChannelRequest(channel)
        )

        linked_chat_id = full.full_chat.linked_chat_id

        if not linked_chat_id:
            return None

        return await telegram_client.get_entity(linked_chat_id)
    except Exception:
        return None


async def comments_are_available(channel):
    discussion_chat = await get_discussion_chat(channel)

    if discussion_chat is None:
        return False

    try:
        await telegram_client.get_permissions(discussion_chat, "me")
        return True
    except Exception:
        return False


async def calculate_channel_rating(entity):
    subscribers = 0
    views = []
    comments = 0
    posts_count = 0
    since = datetime.now(timezone.utc) - timedelta(days=DAYS_TO_PARSE)

    try:
        full = await telegram_client(
            GetFullChannelRequest(entity)
        )
        subscribers = (
            getattr(full.full_chat, "participants_count", None)
            or getattr(entity, "participants_count", 0)
            or 0
        )
    except Exception:
        subscribers = getattr(entity, "participants_count", 0) or 0

    async for post in telegram_client.iter_messages(entity, limit=50):
        post_date = post.date

        if post_date and post_date.tzinfo is None:
            post_date = post_date.replace(tzinfo=timezone.utc)

        if post_date and post_date < since:
            break

        posts_count += 1
        views.append(getattr(post, "views", 0) or 0)

        if post.replies:
            comments += getattr(post.replies, "replies", 0) or 0

    subscriber_score = min(100, int(subscribers / 10000))
    activity_score = min(100, posts_count * 10)
    comments_score = min(100, comments // 2)
    average_views = sum(views) // len(views) if views else 0
    views_score = min(100, int(average_views / 1000))

    total = int(
        subscriber_score * 0.25
        + activity_score * 0.25
        + comments_score * 0.25
        + views_score * 0.25
    )

    db.execute("""
        INSERT INTO channel_ratings (
            chat_id,
            title,
            subscribers_score,
            activity_score,
            comments_score,
            views_score,
            total_score
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            title = excluded.title,
            subscribers_score = excluded.subscribers_score,
            activity_score = excluded.activity_score,
            comments_score = excluded.comments_score,
            views_score = excluded.views_score,
            total_score = excluded.total_score,
            updated_at = CURRENT_TIMESTAMP
    """, (
        entity.id,
        get_public_chat_name(entity),
        subscriber_score,
        activity_score,
        comments_score,
        views_score,
        total,
    ))

    db.commit()
    return total


def save_user(
    user,
    entity,
    message,
    message_link,
    is_admin,
    possible_bot,
    bot_reasons,
):
    old_row = db.execute("""
        SELECT comment_count
        FROM users
        WHERE telegram_id = ?
    """, (user.id,)).fetchone()

    comment_count = (
        (old_row["comment_count"] if old_row else 0) + 1
    )

    user_rating = calculate_user_rating(
        user,
        comment_count,
        is_admin,
    )

    values = (
        getattr(user, "username", None),
        getattr(user, "first_name", "") or "",
        getattr(user, "last_name", "") or "",
        int(bool(getattr(user, "deleted", False))),
        int(bool(getattr(user, "premium", False))),
        get_last_seen_category(user),
        int(is_admin),
        int(possible_bot),
        bot_reasons,
        user_rating,
        getattr(entity, "id", None),
        get_public_chat_name(entity),
        getattr(message, "id", None),
        message_link,
        user.id,
    )

    if old_row:
        db.execute("""
            UPDATE users
            SET
                username = COALESCE(?, username),
                first_name = ?,
                last_name = ?,
                deleted = ?,
                premium = ?,
                last_seen = ?,
                is_admin = ?,
                possible_bot = ?,
                bot_reasons = ?,
                user_rating = ?,
                source_chat_id = ?,
                source_chat_title = ?,
                source_message_id = COALESCE(?, source_message_id),
                source_message_link = COALESCE(?, source_message_link),
                comment_count = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        """, values[:10] + values[10:])
    else:
        db.execute("""
            INSERT INTO users (
                telegram_id,
                username,
                first_name,
                last_name,
                deleted,
                premium,
                last_seen,
                is_admin,
                possible_bot,
                bot_reasons,
                user_rating,
                source_chat_id,
                source_chat_title,
                source_message_id,
                source_message_link,
                comment_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user.id,
            values[0],
            values[1],
            values[2],
            values[3],
            values[4],
            values[5],
            values[6],
            values[7],
            values[8],
            values[9],
            values[10],
            values[11],
            values[12],
            values[13],
        ))

    db.commit()


async def parse_comments_last_two_days(entity):
    processed_messages = 0
    collected_users = 0
    admin_cache = {}

    since = datetime.now(timezone.utc) - timedelta(days=DAYS_TO_PARSE)

    async for post in telegram_client.iter_messages(entity, limit=None):
        if not post.date:
            continue

        post_date = post.date

        if post_date.tzinfo is None:
            post_date = post_date.replace(tzinfo=timezone.utc)

        if post_date < since:
            break

        already_processed = db.execute("""
            SELECT 1
            FROM processed_posts
            WHERE chat_id = ? AND post_id = ?
        """, (entity.id, post.id)).fetchone()

        if already_processed:
            continue

        try:
            if post.replies and post.replies.comments:
                async for comment in telegram_client.iter_messages(
                    entity,
                    reply_to=post.id,
                ):
                    user = await comment.get_sender()

                    if not user:
                        continue

                    excluded = db.execute("""
                        SELECT 1
                        FROM excluded_users
                        WHERE telegram_id = ?
                    """, (user.id,)).fetchone()

                    if excluded:
                        continue

                    old_row = db.execute("""
                        SELECT comment_count
                        FROM users
                        WHERE telegram_id = ?
                    """, (user.id,)).fetchone()

                    old_count = old_row["comment_count"] if old_row else 0
                    comment_text = comment.message or ""

                    possible_bot, bot_reasons = detect_possible_bot(
                        user,
                        [comment_text],
                    )

                    if user.id not in admin_cache:
                        admin_cache[user.id] = await check_is_admin(
                            entity,
                            user.id,
                        )

                    save_user(
                        user=user,
                        entity=entity,
                        message=comment,
                        message_link=await make_message_link(
                            entity,
                            comment.id,
                        ),
                        is_admin=admin_cache[user.id],
                        possible_bot=possible_bot,
                        bot_reasons=bot_reasons,
                    )

                    processed_messages += 1

                    if old_count == 0:
                        collected_users += 1

                    await asyncio.sleep(0.3)

            db.execute("""
                INSERT OR IGNORE INTO processed_posts (chat_id, post_id)
                VALUES (?, ?)
            """, (entity.id, post.id))
            db.commit()

        except FloodWaitError as error:
            print(f"Telegram требует паузу {error.seconds} секунд.")
            await asyncio.sleep(error.seconds)

        except Exception as error:
            print(f"Ошибка обработки поста {post.id}: {error}")

        await asyncio.sleep(1)

    return processed_messages, collected_users


def get_unassigned_users():
    return db.execute("""
        SELECT
            telegram_id,
            username,
            deleted,
            premium,
            is_admin,
            possible_bot,
            bot_reasons,
            user_rating,
            source_message_link
        FROM users
        WHERE assigned = 0
          AND NOT EXISTS (
              SELECT 1
              FROM excluded_users
              WHERE excluded_users.telegram_id = users.telegram_id
          )
        ORDER BY id
        LIMIT ?
    """, (TARGET_USERS,)).fetchall()


async def distribute_users():
    async with distribution_lock:
        rows = get_unassigned_users()

        if len(rows) < TARGET_USERS:
            return False

        for index, recipient_id in enumerate(RECIPIENT_IDS):
            start = index * BATCH_SIZE
            end = start + BATCH_SIZE
            batch = rows[start:end]

            text = "\n\n".join(
                make_result_line(row)
                for row in batch
            )

            try:
                await bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    disable_web_page_preview=True,
                )
                await asyncio.sleep(1)
            except Exception as error:
                print(
                    f"Не удалось отправить пачку "
                    f"{recipient_id}: {error}"
                )
                return False

        db.executemany("""
            UPDATE users
            SET assigned = 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        """, [(row["telegram_id"],) for row in rows])

        db.commit()
        print(f"Распределено пользователей: {len(rows)}")
        return True


async def parse_one_source(entity):
    title = get_public_chat_name(entity)

    try:
        if not await has_recent_posts(entity, DAYS_TO_PARSE):
            print(f"{title}: нет постов за последние {DAYS_TO_PARSE} дня.")
            return 0, 0, 0

        if not await comments_are_available(entity):
            print(f"{title}: комментарии недоступны.")
            return 0, 0, 0

        channel_rating = await calculate_channel_rating(entity)
        print(f"Начинаю обработку: {title}")

        processed, new_users = await parse_comments_last_two_days(entity)

        print(
            f"{title}: комментариев {processed}, "
            f"новых пользователей {new_users}, "
            f"рейтинг канала {rating_text(channel_rating)}"
        )

        return processed, new_users, channel_rating

    except FloodWaitError as error:
        print(f"FloodWait для {title}: {error.seconds} секунд.")
        await asyncio.sleep(error.seconds)
        return 0, 0, 0

    except Exception as error:
        print(f"Ошибка источника {title}: {error}")
        return 0, 0, 0


def get_final_rating_text():
    channel_rows = db.execute("""
        SELECT title, total_score
        FROM channel_ratings
        ORDER BY total_score DESC
    """).fetchall()

    user_row = db.execute("""
        SELECT AVG(user_rating) AS average_rating
        FROM users
        WHERE assigned = 0
          AND NOT EXISTS (
              SELECT 1
              FROM excluded_users
              WHERE excluded_users.telegram_id = users.telegram_id
          )
    """).fetchone()

    average_user_rating = int(user_row["average_rating"] or 0)
    lines = [
        "Итоговый рейтинг пользователей: "
        f"{rating_text(average_user_rating)}"
    ]

    if channel_rows:
        lines.append("\nРейтинг каналов:")
        lines.extend(
            f"{row['title']}: {rating_text(row['total_score'])}"
            for row in channel_rows[:20]
        )

    return "\n".join(lines)


async def auto_parsing_worker():
    global parsing_started_at
    global parsing_deadline

    parsing_started_at = datetime.now(timezone.utc)
    parsing_deadline = parsing_started_at + timedelta(hours=PARSING_HOURS)

    await notify_authorized_users(
        "Автоматический парсинг запущен на 6 часов."
    )

    try:
        while datetime.now(timezone.utc) < parsing_deadline:
            current_count = get_unassigned_count()

            if current_count >= TARGET_USERS:
                if await distribute_users():
                    await notify_authorized_users(
                        "Набрано 300 пользователей. "
                        "Они распределены между шестью операторами."
                    )

            current_count = get_unassigned_count()

            if current_count < TARGET_USERS:
                shortage = TARGET_USERS - current_count

                await notify_authorized_users(
                    f"Нехватка пользователей: {shortage}.\n"
                    f"Сейчас доступно: {current_count}/{TARGET_USERS}.\n"
                    "Беру каналы из папки Stay."
                )

                try:
                    channels = await get_channels_from_stay()
                except Exception as error:
                    print(f"Ошибка получения папки Stay: {error}")
                    channels = []

                if not channels:
                    await notify_authorized_users(
                        "В папке Stay не найдено доступных каналов."
                    )

                for channel in channels:
                    if datetime.now(timezone.utc) >= parsing_deadline:
                        break

                    if get_unassigned_count() >= TARGET_USERS:
                        break

                    await parse_one_source(channel)

            current_count = get_unassigned_count()

            if current_count >= TARGET_USERS:
                if await distribute_users():
                    await notify_authorized_users(
                        "Очередные 300 пользователей распределены."
                    )
            else:
                shortage = TARGET_USERS - current_count
                await notify_authorized_users(
                    f"Промежуточный результат: "
                    f"{current_count}/{TARGET_USERS}.\n"
                    f"Не хватает: {shortage}."
                )

            remaining_seconds = (
                parsing_deadline - datetime.now(timezone.utc)
            ).total_seconds()

            if remaining_seconds <= 0:
                break

            await asyncio.sleep(
                min(STATUS_INTERVAL_SECONDS, remaining_seconds)
            )

    finally:
        await notify_authorized_users(get_final_rating_text())
        parsing_started_at = None
        parsing_deadline = None
        await notify_authorized_users(
            "Автоматический парсинг завершён."
        )


async def start_auto_parsing():
    global parsing_task

    if parsing_task and not parsing_task.done():
        return False

    parsing_task = asyncio.create_task(auto_parsing_worker())
    return True


@dp.message(Command("start"))
async def start_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer(
            "Твой Telegram ID не добавлен в список операторов."
        )
        return

    await message.answer(
        "Бот готов.\n\n"
        "/auto — запустить парсинг на 6 часов\n"
        "/status — показать статус и время\n"
        "/stay — обработать каналы из Stay\n"
        "/pars ссылка — обработать один источник\n"
        "/try — показать 50 пользователей\n"
        "/count — показать количество\n\n"
        "Можно отправить до 100 ссылок пользователей одним сообщением "
        "для добавления в базу исключений."
    )


@dp.message(Command("auto"))
async def auto_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    if not await start_auto_parsing():
        await message.answer("Автоматический парсинг уже запущен.")
        return

    await message.answer(
        "Автоматический парсинг запущен на 6 часов."
    )


@dp.message(Command("status"))
async def status_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    state = (
        "запущен"
        if parsing_task and not parsing_task.done()
        else "не запущен"
    )
    count = get_unassigned_count()

    await message.answer(
        f"Статус: {state}\n"
        f"{get_remaining_time_text()}\n"
        f"Пользователей: {count}/{TARGET_USERS}\n"
        f"Не хватает: {max(0, TARGET_USERS - count)}"
    )


@dp.message(Command("count"))
async def count_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    await message.answer(
        f"Новых пользователей: {get_unassigned_count()}/{TARGET_USERS}"
    )


@dp.message(Command("stay"))
async def stay_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    if parsing_task and not parsing_task.done():
        await message.answer("Уже работает автоматический парсинг.")
        return

    await message.answer("Проверяю каналы из папки Stay.")

    try:
        channels = await get_channels_from_stay()
        total_processed = 0
        total_new_users = 0

        for channel in channels:
            processed, new_users, _ = await parse_one_source(channel)
            total_processed += processed
            total_new_users += new_users

        await message.answer(
            "Обработка завершена.\n"
            f"Комментариев: {total_processed}\n"
            f"Новых пользователей: {total_new_users}\n\n"
            f"{get_final_rating_text()}"
        )

        await distribute_users()

    except Exception as error:
        await message.answer(f"Ошибка:\n{error}")


@dp.message(Command("pars"))
async def pars_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    if parsing_task and not parsing_task.done():
        await message.answer("Уже работает автоматический парсинг.")
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Укажи источник:\n\n"
            "/pars https://t.me/example\n"
            "/pars @example\n"
            "/pars Название группы\n"
            "/pars -1001234567890"
        )
        return

    await message.answer("Ищу группу или канал...")

    try:
        entity = await resolve_source(parts[1].strip())
        title = get_public_chat_name(entity)

        await message.answer(
            f"Источник найден: {title}\n"
            "Обрабатываю комментарии."
        )

        processed, new_users, channel_rating = (
            await parse_one_source(entity)
        )

        await message.answer(
            "Обработка завершена.\n"
            f"Комментариев: {processed}\n"
            f"Новых пользователей: {new_users}\n"
            f"Рейтинг канала: {rating_text(channel_rating)}\n\n"
            f"{get_final_rating_text()}"
        )

        if await distribute_users():
            await message.answer(
                "300 пользователей распределены по шести пачкам."
            )

    except Exception as error:
        await message.answer(f"Ошибка:\n{error}")


@dp.message(Command("try"))
async def try_command(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("Нет доступа.")
        return

    rows = db.execute("""
        SELECT
            telegram_id,
            username,
            deleted,
            premium,
            is_admin,
            possible_bot,
            bot_reasons,
            user_rating,
            source_message_link
        FROM users
        WHERE assigned = 0
          AND NOT EXISTS (
              SELECT 1
              FROM excluded_users
              WHERE excluded_users.telegram_id = users.telegram_id
          )
        ORDER BY id
        LIMIT 50
    """).fetchall()

    if not rows:
        await message.answer("Новых пользователей нет.")
        return

    await message.answer(
        "\n\n".join(make_result_line(row) for row in rows),
        disable_web_page_preview=True,
    )
print(type(API_ID), API_ID)
print(repr(API_HASH), len(API_HASH))
print(repr(PHONE))


@dp.message()
async def links_command(message: Message):
    if not is_authorized(message.from_user.id):
        return

    links = extract_user_links(message.text or "")

    if not links:
        return

    if len(links) > 100:
        await message.answer(
            f"Найдено ссылок: {len(links)}. "
            "За одно сообщение можно отправить не более 100."
        )
        return

    added, duplicates = await add_excluded_links(links)

    await message.answer(
        f"Добавлено в базу исключений: {added}\n"
        f"Дубликатов: {duplicates}"
    )
telegram_client = TelegramClient(
    "telegram_profile",
    API_ID,
    API_HASH,
    connection_retries=10,
    retry_delay=5,
    timeout=30,
)


async def main():
    init_db()

    print("Авторизация Telegram-профиля...")
    await telegram_client.start(phone=PHONE)

    me = await telegram_client.get_me()

    print(
        f"Профиль подключён: "
        f"{me.first_name or ''} "
        f"@{me.username or 'без_username'}"
    )
    print("Бот запущен.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await telegram_client.disconnect()
        db.close()

load_dotenv()

print("API_ID:", API_ID)
print("API_HASH задан:", bool(API_HASH))
print("PHONE:", PHONE)

import sys
print(sys.executable)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановка программы.")


