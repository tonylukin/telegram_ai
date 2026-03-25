import json
import uuid
import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from boto3.dynamodb.conditions import Key
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from app.bots.dishscan.completions_loop import (
    completions_loop,
    record_meal_for_user,
)
from app.bots.dishscan.date_helpers import now_iso, DEFAULT_USER_TIMEZONE, today_local_date, sha256_hex, \
    parse_history_date_arg, HISTORY_LIMIT, parse_utc_offset_to_tzinfo, normalize_utc_offset, history_date_hint
from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.bots.dishscan.string_helpers import extract_meal_title, to_decimal, build_today_text, build_history_text
from app.bots.utils import get_user_info_from_update
from app.config import TELEGRAM_DISHSCAN_BOT_TOKEN
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from config import settings
from aws_clients import s3, sqs, events, dynamodb

jobs_table = dynamodb.Table(settings.ddb_jobs_table_name)
image_cache_table = dynamodb.Table(settings.ddb_image_cache_table_name)
user_history_table = dynamodb.Table(settings.ddb_user_history_table_name)


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


def get_last_meal(chat_id: int) -> dict | None:
    resp = user_history_table.query(
        KeyConditionExpression=(
            Key("pk").eq(f"USER#{chat_id}") & Key("sk").begins_with("MEAL#")
        ),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def clamp_day_totals(chat_id: int, local_date: str) -> None:
    day_key = {"pk": f"USER#{chat_id}", "sk": f"DAY#{local_date}"}
    resp = user_history_table.get_item(Key=day_key)
    item = resp.get("Item")
    if not item:
        return

    total_calories = max(to_decimal(item.get("total_calories", 0)), Decimal("0"))
    total_protein = max(to_decimal(item.get("total_protein_g", 0)), Decimal("0"))
    total_fat = max(to_decimal(item.get("total_fat_g", 0)), Decimal("0"))
    total_carbs = max(to_decimal(item.get("total_carbs_g", 0)), Decimal("0"))
    meals_count = max(to_decimal(item.get("meals_count", 0)), Decimal("0"))

    user_history_table.update_item(
        Key=day_key,
        UpdateExpression="""
            SET total_calories = :calories,
                total_protein_g = :protein,
                total_fat_g = :fat,
                total_carbs_g = :carbs,
                meals_count = :meals_count,
                updated_at = :updated_at
        """,
        ExpressionAttributeValues={
            ":calories": total_calories,
            ":protein": total_protein,
            ":fat": total_fat,
            ":carbs": total_carbs,
            ":meals_count": meals_count,
            ":updated_at": now_iso(),
        },
    )


def delete_last_meal_for_user(chat_id: int) -> dict | None:
    meal_item = get_last_meal(chat_id)
    if not meal_item:
        return None

    pk = str(meal_item["pk"])
    sk = str(meal_item["sk"])
    local_date = str(meal_item.get("local_date") or sk.split("#")[1])
    day_sk = f"DAY#{local_date}"

    calories = to_decimal(meal_item.get("calories", 0))
    protein = to_decimal(meal_item.get("protein_g", 0))
    fat = to_decimal(meal_item.get("fat_g", 0))
    carbs = to_decimal(meal_item.get("carbs_g", 0))

    day_resp = user_history_table.get_item(
        Key={"pk": f"USER#{chat_id}", "sk": day_sk}
    )
    day_item = day_resp.get("Item")
    if not day_item:
        raise ValueError(f"DAY item not found for chat_id={chat_id}, local_date={local_date}")

    new_total_calories = max(
        to_decimal(day_item.get("total_calories", 0)) - calories,
        Decimal("0"),
    )
    new_total_protein = max(
        to_decimal(day_item.get("total_protein_g", 0)) - protein,
        Decimal("0"),
    )
    new_total_fat = max(
        to_decimal(day_item.get("total_fat_g", 0)) - fat,
        Decimal("0"),
    )
    new_total_carbs = max(
        to_decimal(day_item.get("total_carbs_g", 0)) - carbs,
        Decimal("0"),
    )
    new_meals_count = max(
        to_decimal(day_item.get("meals_count", 0)) - Decimal("1"),
        Decimal("0"),
    )

    user_history_table.delete_item(
        Key={"pk": pk, "sk": sk},
        ConditionExpression="attribute_exists(pk) AND attribute_exists(sk)",
    )

    user_history_table.update_item(
        Key={"pk": f"USER#{chat_id}", "sk": day_sk},
        UpdateExpression="""
            SET total_calories = :total_calories,
                total_protein_g = :total_protein_g,
                total_fat_g = :total_fat_g,
                total_carbs_g = :total_carbs_g,
                meals_count = :meals_count,
                updated_at = :updated_at
        """,
        ExpressionAttributeValues={
            ":total_calories": new_total_calories,
            ":total_protein_g": new_total_protein,
            ":total_fat_g": new_total_fat,
            ":total_carbs_g": new_total_carbs,
            ":meals_count": new_meals_count,
            ":updated_at": now_iso(),
        },
        ConditionExpression="attribute_exists(pk) AND attribute_exists(sk)",
    )

    return meal_item


async def delete_last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.effective_message
        chat = update.effective_chat

        if not message or not chat:
            return

        deleted_item = await asyncio.to_thread(
            delete_last_meal_for_user,
            int(chat.id),
        )

        if not deleted_item:
            await message.reply_text("История пуста, удалять нечего.")
            return

        title = extract_meal_title(deleted_item.get("result"))
        local_date = str(
            deleted_item.get("local_date") or str(deleted_item["sk"]).split("#")[1]
        )

        await message.reply_text(
            f"✅ Удалил последнюю запись: *{title}*\n"
            f"Дата: *{local_date}*",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception(e)
        if update.effective_message:
            await update.effective_message.reply_text(
                "Не удалось удалить последнюю запись. Попробуйте ещё раз."
            )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправьте мне фото еды 🍽️, и я оценю калории и макроэлементы.\n"
        "Совет: попробуйте сделать чёткий снимок сверху.\n\n"
        "Команды:\n"
        "/today — сумма калорий и макросов за сегодня\n"
        f"/history {history_date_hint()} — история приёмов пищи за дату\n"
        "/delete_last — удалить последнюю запись\n"
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
    application.add_handler(CommandHandler("delete_last", delete_last_cmd))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return application


if __name__ == "__main__":
    app = build_bot_app()
    print("DishScan bot started")
    app.run_polling()