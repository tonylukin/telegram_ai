import json
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from app.bots.dishscan.completions_loop import (
    completions_loop,
    record_meal_for_user,
)
from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.bots.utils import get_user_info_from_update
from app.config import TELEGRAM_DISHSCAN_BOT_TOKEN
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from config import settings
from aws_clients import s3, sqs, events, dynamodb

jobs_table = dynamodb.Table(settings.ddb_jobs_table_name)
image_cache_table = dynamodb.Table(settings.ddb_image_cache_table_name)
user_history_table = dynamodb.Table(settings.ddb_user_history_table_name)

DEFAULT_USER_TIMEZONE = "-08:00"
HISTORY_LIMIT = 20

SUPPORTED_HISTORY_DATE_FORMATS = [
    "%d.%m.%Y",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_utc_offset_to_tzinfo(offset_str: str) -> timezone:
    if not offset_str:
        return timezone(timedelta(hours=-8))

    sign = 1
    raw = offset_str.strip()

    if raw[0] == "-":
        sign = -1
        raw = raw[1:]
    elif raw[0] == "+":
        raw = raw[1:]

    if ":" in raw:
        hours_str, minutes_str = raw.split(":", 1)
        hours = int(hours_str)
        minutes = int(minutes_str)
    else:
        hours = int(raw)
        minutes = 0

    delta = timedelta(hours=hours, minutes=minutes)
    return timezone(sign * delta)


def normalize_utc_offset(raw: str) -> str | None:
    if not raw:
        return None

    value = raw.strip().replace("utc", "").replace("UTC", "").strip()

    try:
        if value[0] not in {"+", "-"}:
            return None

        sign = value[0]
        body = value[1:]

        if ":" in body:
            hours_str, minutes_str = body.split(":", 1)
            hours = int(hours_str)
            minutes = int(minutes_str)
        else:
            hours_float = float(body)
            hours = int(hours_float)
            minutes = int(round((hours_float - hours) * 60))

        if minutes < 0:
            minutes = abs(minutes)

        total_minutes = hours * 60 + minutes
        if total_minutes > 14 * 60:
            return None

        return f"{sign}{hours:02d}:{minutes:02d}"
    except Exception:
        return None


def today_local_date(tz_name: str = DEFAULT_USER_TIMEZONE) -> str:
    tzinfo = parse_utc_offset_to_tzinfo(tz_name)
    return datetime.now(timezone.utc).astimezone(tzinfo).date().isoformat()


def format_num(value) -> str:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        return format(value.normalize(), "f").rstrip("0").rstrip(".")

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value)


def history_date_hint() -> str:
    return "dd.mm.YYYY"


def parse_flexible_date(raw: str, formats: list[str]) -> str | None:
    raw = raw.strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_history_date_arg(args: list[str]) -> str | None:
    if not args:
        return None
    return parse_flexible_date(args[0], SUPPORTED_HISTORY_DATE_FORMATS)


def format_consumed_time_for_user(consumed_at: str, tz_name: str = DEFAULT_USER_TIMEZONE) -> str:
    if not consumed_at:
        return "--:--"

    try:
        dt_utc = datetime.fromisoformat(consumed_at)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        tzinfo = parse_utc_offset_to_tzinfo(tz_name)
        dt_local = dt_utc.astimezone(tzinfo)
        return dt_local.strftime("%H:%M")
    except Exception as e:
        logger.exception(e)
        return "--:--"


def get_user_timezone(chat_id: int) -> str:
    try:
        resp = user_history_table.get_item(
            Key={"pk": f"USER#{chat_id}", "sk": "PROFILE"}
        )
        item = resp.get("Item")
        if item and item.get("timezone"):
            return str(item["timezone"])
    except Exception:
        pass

    return DEFAULT_USER_TIMEZONE


def set_user_timezone(chat_id: int, timezone_name: str) -> None:
    now = now_iso()
    existing = user_history_table.get_item(
        Key={"pk": f"USER#{chat_id}", "sk": "PROFILE"}
    ).get("Item")

    created_at = existing.get("created_at", now) if existing else now

    user_history_table.put_item(
        Item={
            "pk": f"USER#{chat_id}",
            "sk": "PROFILE",
            "type": "PROFILE",
            "chat_id": int(chat_id),
            "timezone": timezone_name,
            "created_at": created_at,
            "updated_at": now,
        }
    )


def build_today_text(day_item: dict | None, local_date: str) -> str:
    if not day_item:
        return (
            f"📊 За сегодня ({local_date}) пока ничего не записано.\n"
            f"Отправьте фото еды, и я начну вести историю."
        )

    total_calories = day_item.get("total_calories", 0)
    total_protein = day_item.get("total_protein_g", 0)
    total_fat = day_item.get("total_fat_g", 0)
    total_carbs = day_item.get("total_carbs_g", 0)
    meals_count = day_item.get("meals_count", 0)

    return (
        f"📊 *Итого за сегодня* ({local_date})\n\n"
        f"Приёмов пищи: *{format_num(meals_count)}*\n"
        f"Калории: *{format_num(total_calories)} kcal*\n"
        f"Белки: *{format_num(total_protein)} g*\n"
        f"Жиры: *{format_num(total_fat)} g*\n"
        f"Углеводы: *{format_num(total_carbs)} g*"
    )


def extract_meal_title(result: dict | None) -> str:
    if not isinstance(result, dict):
        return "Приём пищи"

    items = result.get("items")
    if isinstance(items, list) and items:
        names = []
        for item in items[:3]:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        if names:
            if len(items) > 3:
                return ", ".join(names) + "…"
            return ", ".join(names)

    if result.get("name"):
        return str(result["name"])

    return "Приём пищи"


def build_history_text(items: list[dict], local_date: str) -> str:
    if not items:
        return f"📝 За дату *{local_date}* история приёмов пищи пуста."

    lines = [f"📝 *История за {local_date}*\n"]

    for idx, item in enumerate(items, start=1):
        result = item.get("result")
        title = extract_meal_title(result)
        calories = format_num(item.get("calories", 0))
        protein = format_num(item.get("protein_g", 0))
        fat = format_num(item.get("fat_g", 0))
        carbs = format_num(item.get("carbs_g", 0))
        consumed_at = str(item.get("consumed_at", ""))
        timezone_name = str(item.get("timezone", DEFAULT_USER_TIMEZONE))

        time_part = format_consumed_time_for_user(consumed_at, timezone_name)

        lines.append(
            f"{idx}. *{title}*\n"
            f"   🕒 {time_part}\n"
            f"   🔥 {calories} kcal | Б {protein} g | Ж {fat} g | У {carbs} g"
        )

    return "\n\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправьте мне фото еды 🍽️, и я оценю калории и макроэлементы.\n"
        "Совет: попробуйте сделать чёткий снимок сверху.\n\n"
        "Команды:\n"
        "/today — сумма калорий и макросов за сегодня\n"
        f"/history {history_date_hint()} — история приёмов пищи за дату\n"
        "/timezone — показать текущую таймзону\n"
        "/timezone -8 — установить UTC offset\n"
        "/timezone +5.5 — установить UTC offset"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat_id = message.chat_id
        user_timezone = await asyncio.to_thread(get_user_timezone, int(chat_id))
        local_date = today_local_date(user_timezone)

        resp = await asyncio.to_thread(
            user_history_table.get_item,
            Key={"pk": f"USER#{chat_id}", "sk": f"DAY#{local_date}"},
        )
        item = resp.get("Item")

        await message.reply_text(
            build_today_text(item, local_date),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception(e)
        await update.message.reply_text(
            "Не удалось получить статистику за сегодня. Попробуйте ещё раз."
        )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat_id = message.chat_id

        local_date = parse_history_date_arg(context.args)
        if not local_date:
            await message.reply_text(
                "Укажите дату в правильном формате.\n"
                f"Пример: /history {datetime.now().strftime('%d.%m.%Y')}"
            )
            return

        resp = await asyncio.to_thread(
            user_history_table.query,
            KeyConditionExpression=(
                Key("pk").eq(f"USER#{chat_id}")
                & Key("sk").begins_with(f"MEAL#{local_date}#")
            ),
            ScanIndexForward=False,
            Limit=HISTORY_LIMIT,
        )

        items = resp.get("Items", [])

        await message.reply_text(
            build_history_text(items, local_date),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception(e)
        await update.message.reply_text(
            "Не удалось получить историю приёмов пищи. Попробуйте ещё раз."
        )


async def timezone_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        chat = update.effective_chat

        if not message or not chat:
            return

        chat_id = int(chat.id)

        if not context.args:
            current_tz = await asyncio.to_thread(get_user_timezone, chat_id)
            current_time = datetime.now(timezone.utc).astimezone(
                parse_utc_offset_to_tzinfo(current_tz)
            ).strftime("%d.%m.%Y %H:%M")
            await message.reply_text(
                f"Текущий UTC offset: *{current_tz}*\n"
                f"Локальное время: *{current_time}*\n\n"
                f"Чтобы изменить, отправьте команду в виде:\n"
                f"`/timezone -8`\n"
                f"`/timezone +3`\n"
                f"`/timezone +5.5`",
                parse_mode="Markdown",
            )
            return

        raw_tz = "".join(context.args).strip()
        timezone_name = normalize_utc_offset(raw_tz)

        if not timezone_name:
            await message.reply_text(
                "Не удалось распознать UTC offset.\n"
                "Примеры:\n"
                "`/timezone -8`\n"
                "`/timezone +3`\n"
                "`/timezone +5.5`\n"
                "`/timezone +09:00`",
                parse_mode="Markdown",
            )
            return

        await asyncio.to_thread(set_user_timezone, chat_id, timezone_name)

        current_time = datetime.now(timezone.utc).astimezone(
            parse_utc_offset_to_tzinfo(timezone_name)
        ).strftime("%d.%m.%Y %H:%M")

        await message.reply_text(
            f"✅ UTC offset сохранён: *{timezone_name}*\n"
            f"Локальное время: *{current_time}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception(e)
        if update.effective_message:
            await update.effective_message.reply_text(
                "Не удалось сохранить таймзону. Попробуйте ещё раз."
            )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat_id = message.chat_id
        user = get_user_info_from_update(update)

        if not message.photo:
            await message.reply_text("Пожалуйста, отправьте фотографию блюда.")
            return

        photo = message.photo[-1]
        await message.reply_text("Получил фото, обрабатываю... ⏳")

        tg_file = await context.bot.get_file(photo.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        image_bytes = bytes(file_bytes)

        image_hash = sha256_hex(image_bytes)
        user_timezone = await asyncio.to_thread(get_user_timezone, int(chat_id))

        cache_resp = await asyncio.to_thread(
            image_cache_table.get_item,
            Key={"image_hash": image_hash},
        )
        cache_item = cache_resp.get("Item")

        if (
            cache_item
            and cache_item.get("status") == "READY"
            and cache_item.get("cache_version") == settings.image_cache_version
            and cache_item.get("result") is not None
        ):
            cached_result = cache_item["result"]

            await asyncio.to_thread(
                record_meal_for_user,
                user_history_table,
                int(chat_id),
                f"cache-{uuid.uuid4()}",
                image_hash,
                cached_result,
                user_timezone,
            )

            text = format_markdown(cached_result)
            await message.reply_text(text, parse_mode="Markdown")
            return

        job_id = str(uuid.uuid4())
        s3_key = f"uploads/{chat_id}/{job_id}.jpg"

        s3.put_object(
            Bucket=settings.s3_bucket,
            Key=s3_key,
            Body=image_bytes,
            ContentType="image/jpeg",
            Metadata={
                "job_id": job_id,
                "telegram_chat_id": str(chat_id),
                "image_hash": image_hash,
                "cache_version": str(settings.image_cache_version),
            },
        )

        now = now_iso()
        await asyncio.to_thread(
            jobs_table.put_item,
            Item={
                "pk": f"JOB#{job_id}",
                "sk": "META",
                "job_id": job_id,
                "chat_id": int(chat_id),
                "s3_bucket": settings.s3_bucket,
                "s3_key": s3_key,
                "image_hash": image_hash,
                "cache_version": settings.image_cache_version,
                "user_timezone": user_timezone,
                "user": user,
                "status": "PENDING",
                "created_at": now,
                "updated_at": now,
            },
        )

        payload = {
            "job_id": job_id,
            "chat_id": int(chat_id),
            "s3_bucket": settings.s3_bucket,
            "s3_key": s3_key,
            "image_hash": image_hash,
            "cache_version": settings.image_cache_version,
            "user_timezone": user_timezone,
            "received_at": now_iso(),
            "version": 1,
        }

        sqs.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(payload),
            MessageAttributes={
                "eventType": {"StringValue": "DishScanUploaded", "DataType": "String"},
                "jobId": {"StringValue": job_id, "DataType": "String"},
            },
        )

        events.put_events(Entries=[{
            "EventBusName": settings.event_bus_name,
            "Source": "dishscan.telegram",
            "DetailType": "DishScanUploaded",
            "Time": datetime.now(timezone.utc),
            "Detail": json.dumps(payload),
        }])

        await message.reply_text(
            "Обрабатываю ваше фото! Это может занять около 30 секунд. Я сообщу вам, когда будет готово.",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception(e)
        await update.message.reply_text(
            "Упс, что-то пошло не так при обработке вашего фото. Пожалуйста, попробуйте снова."
        )


def build_bot_app() -> Application:
    application = Application.builder().token(TELEGRAM_DISHSCAN_BOT_TOKEN).build()
    application.bot_data["completions_task"] = None
    notification_sender = NotificationSender()

    async def post_init(app: Application) -> None:
        app.bot_data["completions_task"] = asyncio.create_task(
            completions_loop(app, notification_sender),
            name="dishscan-completions-loop",
        )

    async def post_shutdown(app: Application) -> None:
        task = app.bot_data.get("completions_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    application.post_init = post_init
    application.post_shutdown = post_shutdown

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("history", history))
    application.add_handler(CommandHandler("timezone", timezone_cmd))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return application


if __name__ == "__main__":
    app = build_bot_app()
    print("DishScan bot started")
    app.run_polling()