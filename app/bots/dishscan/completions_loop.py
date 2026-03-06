import asyncio
import json
import os
from telegram.ext import Application

from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from aws_clients import dynamodb as ddb, sqs

AWS_REGION = os.environ["DISHSCAN_AWS_REGION"]
DDB_TABLE_NAME = os.environ["DISHSCAN_DDB_TABLE_NAME"]
COMPLETIONS_QUEUE_URL = os.environ["DISHSCAN_COMPLETIONS_QUEUE_URL"]

table = ddb.Table(DDB_TABLE_NAME)


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
                    print(f'job_id: {job_id}, status: {status}')

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
                            text = format_markdown(result)
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
