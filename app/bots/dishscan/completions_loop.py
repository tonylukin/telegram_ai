import asyncio
import json
import os
from datetime import datetime, timezone
from telegram.ext import Application

from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from aws_clients import dynamodb as ddb, sqs

AWS_REGION = os.environ["DISHSCAN_AWS_REGION"]
DDB_TABLE_NAME = os.environ["DISHSCAN_DDB_TABLE_NAME"]
COMPLETIONS_QUEUE_URL = os.environ["DISHSCAN_COMPLETIONS_QUEUE_URL"]

table = ddb.Table(DDB_TABLE_NAME)
CACHE_VERSION = 1

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def completions_loop(app: Application, notification_sender: NotificationSender):
    try:
        while True:
            try:
                resp = await asyncio.to_thread(
                    sqs.receive_message,
                    QueueUrl=COMPLETIONS_QUEUE_URL,
                    MaxNumberOfMessages=10,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=60,
                )

                for msg in resp.get("Messages", []):
                    try:
                        body = json.loads(msg["Body"])
                    except Exception:
                        # bad message -> delete
                        await asyncio.to_thread(
                            sqs.delete_message,
                            QueueUrl=COMPLETIONS_QUEUE_URL,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                        continue

                    detail = body.get("detail")
                    if isinstance(detail, str):
                        detail = json.loads(detail)
                    elif detail is None:
                        detail = {}

                    job_id = detail.get("job_id") or body.get("job_id")
                    status = detail.get("status") or body.get("status")
                    print(f"job_id: {job_id}, status: {status}")

                    if not job_id:
                        await asyncio.to_thread(
                            sqs.delete_message,
                            QueueUrl=COMPLETIONS_QUEUE_URL,
                            ReceiptHandle=msg["ReceiptHandle"],
                        )
                        continue

                    ddb_resp = await asyncio.to_thread(
                        table.get_item,
                        Key={"pk": f"JOB#{job_id}", "sk": "META"},
                    )
                    item = ddb_resp.get("Item", {})
                    chat_id = item.get("chat_id")

                    if chat_id:
                        if status == "DONE":
                            result = item.get("result")
                            text = format_markdown(result) if result is not None else "❌ Error: Empty result"

                            # ---- write cache on success (best effort) ----
                            image_hash = item.get("image_hash")
                            cache_version = item.get("cache_version", CACHE_VERSION)

                            if image_hash and result is not None:
                                try:
                                    # Upsert cache item
                                    await asyncio.to_thread(
                                        table.put_item,
                                        Item={
                                            "pk": f"CACHE#{image_hash}",
                                            "sk": "META",
                                            "status": "READY",
                                            "cache_version": int(cache_version),
                                            "result": result,
                                            "created_at": now_iso(),
                                            "updated_at": now_iso(),
                                        },
                                    )
                                except Exception as e:
                                    logger.exception(f"cache put_item failed: {e}")

                        else:
                            text = f"❌ Error: {item.get('error', 'Unknown error')}"

                        # async telegram send
                        await app.bot.send_message(chat_id=int(chat_id), text=text, parse_mode="Markdown")
                        notification_message = f"DishScan:\n<blockquote>{text}</blockquote>"
                        await notification_sender.send_notification_message(notification_message)

                    await asyncio.to_thread(
                        sqs.delete_message,
                        QueueUrl=COMPLETIONS_QUEUE_URL,
                        ReceiptHandle=msg["ReceiptHandle"],
                    )

                    await asyncio.sleep(0.2)

            except Exception as e:
                logger.exception(f"completions_loop exception: {e}")
                await asyncio.sleep(2)

    except asyncio.CancelledError:
        print("completions_loop: cancelled")
        return