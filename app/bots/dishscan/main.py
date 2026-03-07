import json
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from app.bots.dishscan.completions_loop import (
    completions_loop,
    record_meal_for_user,
)
from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.config import TELEGRAM_DISHSCAN_BOT_TOKEN
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from config import settings
from aws_clients import s3, sqs, events, dynamodb

jobs_table = dynamodb.Table(settings.ddb_jobs_table_name)
image_cache_table = dynamodb.Table(settings.ddb_image_cache_table_name)
user_history_table = dynamodb.Table(settings.ddb_user_history_table_name)

DEFAULT_USER_TIMEZONE = "America/Los_Angeles"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def today_local_date(tz_name: str = DEFAULT_USER_TIMEZONE) -> str:
    return datetime.now(ZoneInfo(tz_name)).date().isoformat()


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
        f"Приёмов пищи: *{meals_count}*\n"
        f"Калории: *{total_calories} kcal*\n"
        f"Белки: *{total_protein} g*\n"
        f"Жиры: *{total_fat} g*\n"
        f"Углеводы: *{total_carbs} g*"
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправьте мне фото еды 🍽️, и я оценю калории и макроэлементы.\n"
        "Совет: попробуйте сделать чёткий снимок сверху.\n\n"
        "Команды:\n"
        "/today — сумма калорий и макросов за сегодня"
    )


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat_id = message.chat_id
        local_date = today_local_date(DEFAULT_USER_TIMEZONE)

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
        print(f"Error in /today: {e}")
        await update.message.reply_text(
            "Не удалось получить статистику за сегодня. Попробуйте ещё раз."
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.message
        chat_id = message.chat_id

        if not message.photo:
            await message.reply_text("Пожалуйста, отправьте фотографию блюда.")
            return

        # Choose the largest photo variant
        photo = message.photo[-1]
        await message.reply_text("Получил фото, обрабатываю... ⏳")

        # Download bytes from Telegram
        tg_file = await context.bot.get_file(photo.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        image_bytes = bytes(file_bytes)

        # 0) Compute content hash and check cache
        image_hash = sha256_hex(image_bytes)

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

            # даже при cache hit записываем meal в историю пользователя
            await asyncio.to_thread(
                record_meal_for_user,
                user_history_table,
                int(chat_id),
                f"cache-{uuid.uuid4()}",
                image_hash,
                cached_result,
                DEFAULT_USER_TIMEZONE,
            )

            text = format_markdown(cached_result)
            await message.reply_text(text, parse_mode="Markdown")
            return

        # Not cached -> proceed as before
        job_id = str(uuid.uuid4())
        s3_key = f"uploads/{chat_id}/{job_id}.jpg"

        # 1) Upload to S3
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

        # 2) Create a pending status record in DynamoDB
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
                "user_timezone": DEFAULT_USER_TIMEZONE,
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
            "user_timezone": DEFAULT_USER_TIMEZONE,
            "received_at": now_iso(),
            "version": 1,
        }

        # 3) Enqueue to SQS
        sqs.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(payload),
            MessageAttributes={
                "eventType": {"StringValue": "DishScanUploaded", "DataType": "String"},
                "jobId": {"StringValue": job_id, "DataType": "String"},
            },
        )

        # 4) Optional: publish event to EventBridge
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
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return application


if __name__ == "__main__":
    app = build_bot_app()
    print("DishScan bot started")
    app.run_polling()