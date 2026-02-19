import json
import uuid
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from config import settings
from aws_clients import s3, sqs, events, dynamodb

table = dynamodb.Table(settings.ddb_table_name)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a food photo 🍽️ and I'll estimate calories + macros.\n"
        "Tip: try a clear top-down shot."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat_id = message.chat_id

    if not message.photo:
        await message.reply_text("Please send a photo.")
        return

    # Choose the largest photo variant
    photo = message.photo[-1]
    await message.reply_text("Got it ✅ Uploading and queueing analysis…")

    # Download bytes from Telegram
    tg_file = await context.bot.get_file(photo.file_id)
    file_bytes = await tg_file.download_as_bytearray()
    image_bytes = bytes(file_bytes)

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
        "status": "PENDING",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })

    payload = {
        "job_id": job_id,
        "chat_id": int(chat_id),
        "s3_bucket": settings.s3_bucket,
        "s3_key": s3_key,
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
        f"Queued 🧾 Job: `{job_id}`\nI'll reply when it's ready.",
        parse_mode="Markdown"
    )

def build_bot_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    return app

if __name__ == "__main__":
    app = build_bot_app()
    app.run_polling()
