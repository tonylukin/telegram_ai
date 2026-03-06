import json
import uuid
import asyncio
import hashlib
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from app.bots.dishscan.completions_loop import completions_loop, CACHE_VERSION
from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.config import TELEGRAM_DISHSCAN_BOT_TOKEN
from app.services.notification_sender import NotificationSender
from config import settings
from aws_clients import s3, sqs, events, dynamodb

table = dynamodb.Table(settings.ddb_table_name)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Отправьте мне фото еды 🍽️, и я оценю калории и макроэлементы.\n"
        "Совет: попробуйте сделать чёткий снимок сверху."
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

        cache_resp = table.get_item(Key={"pk": f"CACHE#{image_hash}", "sk": "META"})
        cache_item = cache_resp.get("Item")

        if (
            cache_item
            and cache_item.get("status") == "READY"
            and cache_item.get("cache_version") == CACHE_VERSION
            and cache_item.get("result") is not None
        ):
            # Serve cached result immediately
            cached_result = cache_item["result"]
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
                "cache_version": str(CACHE_VERSION),
            },
        )

        # 2) Create a pending status record in DynamoDB
        table.put_item(Item={
            "pk": f"JOB#{job_id}",
            "sk": "META",
            "job_id": job_id,
            "chat_id": int(chat_id),
            "s3_bucket": settings.s3_bucket,
            "s3_key": s3_key,
            "image_hash": image_hash,          # <--- needed for caching later
            "cache_version": CACHE_VERSION,    # <--- for invalidation
            "status": "PENDING",
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })

        payload = {
            "job_id": job_id,
            "chat_id": int(chat_id),
            "s3_bucket": settings.s3_bucket,
            "s3_key": s3_key,
            "image_hash": image_hash,
            "cache_version": CACHE_VERSION,
            "received_at": now_iso(),
            "version": 1,
        }

        # 3) Enqueue to SQS (DLQ is configured on the queue with redrive policy)
        sqs.send_message(
            QueueUrl=settings.sqs_queue_url,
            MessageBody=json.dumps(payload),
            MessageAttributes={
                "eventType": {"StringValue": "DishScanUploaded", "DataType": "String"},
                "jobId": {"StringValue": job_id, "DataType": "String"},
            },
        )

        # 4) Optional: publish event to EventBridge (event sourcing / audit)
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
        print(f"Error in handle_photo: {e}")
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
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return application


if __name__ == "__main__":
    app = build_bot_app()
    print("DishScan bot started")
    app.run_polling()