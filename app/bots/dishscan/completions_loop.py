import asyncio
import json
import os
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from botocore.exceptions import ClientError
from telegram.ext import Application

from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from aws_clients import dynamodb, sqs
from config import settings

COMPLETIONS_QUEUE_URL = os.environ["DISHSCAN_COMPLETIONS_QUEUE_URL"]

jobs_table = dynamodb.Table(settings.ddb_jobs_table_name)
image_cache_table = dynamodb.Table(settings.ddb_image_cache_table_name)
user_history_table = dynamodb.Table(settings.ddb_user_history_table_name)

DEFAULT_USER_TIMEZONE = "-08:00"
CACHE_TTL_DAYS = 30


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return now_utc().isoformat()


def ttl_epoch(days: int = CACHE_TTL_DAYS) -> int:
    return int((now_utc() + timedelta(days=days)).timestamp())


def parse_utc_offset_to_tzinfo(offset_str: str) -> timezone:
    if not offset_str:
        return timezone(timedelta(hours=-8))

    raw = offset_str.strip()
    sign = 1

    if raw.startswith("-"):
        sign = -1
        raw = raw[1:]
    elif raw.startswith("+"):
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


def to_local_date(utc_dt: datetime, tz_name: str) -> str:
    tzinfo = parse_utc_offset_to_tzinfo(tz_name)
    return utc_dt.astimezone(tzinfo).date().isoformat()


def safe_number(value, default=0):
    if value is None:
        return default

    if isinstance(value, Decimal):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, str):
        cleaned = value.strip().lower().replace(",", "")
        match = re.search(r"-?\d+(\.\d+)?", cleaned)
        if not match:
            return default

        number_str = match.group(0)
        try:
            return Decimal(number_str)
        except Exception:
            return default

    return default


def result_macros(result: dict) -> dict:
    total = result.get("total") if isinstance(result.get("total"), dict) else {}

    return {
        "calories": safe_number(total.get("calories"), 0),
        "protein_g": safe_number(total.get("protein_g"), 0),
        "fat_g": safe_number(total.get("fat_g"), 0),
        "carbs_g": safe_number(total.get("carbs_g"), 0),
    }


def to_ddb_number(value):
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def record_meal_for_user(
    table,
    chat_id: int,
    job_id: str,
    image_hash: str | None,
    result: dict,
    user_timezone: str = DEFAULT_USER_TIMEZONE,
) -> bool:
    """
    Creates MEAL entry once and updates DAY aggregate only if the MEAL was newly inserted.
    Returns True if a new meal was recorded, False if it was already recorded before.
    """
    consumed_at_dt = now_utc()
    consumed_at = consumed_at_dt.isoformat()
    local_date = to_local_date(consumed_at_dt, user_timezone)
    macros = result_macros(result)

    meal_item = {
        "pk": f"USER#{chat_id}",
        "sk": f"MEAL#{local_date}#{consumed_at}#{job_id}",
        "type": "MEAL",
        "chat_id": int(chat_id),
        "job_id": job_id,
        "image_hash": image_hash,
        "consumed_at": consumed_at,
        "local_date": local_date,
        "timezone": user_timezone,
        "calories": to_ddb_number(macros["calories"]),
        "protein_g": to_ddb_number(macros["protein_g"]),
        "fat_g": to_ddb_number(macros["fat_g"]),
        "carbs_g": to_ddb_number(macros["carbs_g"]),
        "result": result,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    try:
        table.put_item(
            Item=meal_item,
            ConditionExpression="attribute_not_exists(pk) AND attribute_not_exists(sk)",
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            return False
        raise

    table.update_item(
        Key={"pk": f"USER#{chat_id}", "sk": f"DAY#{local_date}"},
        UpdateExpression=(
            "SET #type = :type, chat_id = :chat_id, local_date = :local_date, "
            "#tz = :tz, updated_at = :updated_at "
            "ADD total_calories :calories, total_protein_g :protein_g, "
            "total_fat_g :fat_g, total_carbs_g :carbs_g, meals_count :one"
        ),
        ExpressionAttributeNames={
            "#type": "type",
            "#tz": "timezone",
        },
        ExpressionAttributeValues={
            ":type": "DAY",
            ":chat_id": int(chat_id),
            ":local_date": local_date,
            ":tz": user_timezone,
            ":updated_at": now_iso(),
            ":calories": to_ddb_number(macros["calories"]),
            ":protein_g": to_ddb_number(macros["protein_g"]),
            ":fat_g": to_ddb_number(macros["fat_g"]),
            ":carbs_g": to_ddb_number(macros["carbs_g"]),
            ":one": Decimal(1),
        },
    )

    return True


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
                        jobs_table.get_item,
                        Key={"pk": f"JOB#{job_id}", "sk": "META"},
                    )
                    item = ddb_resp.get("Item", {})
                    chat_id = item.get("chat_id")
                    user = item.get("user")

                    if chat_id:
                        if status == "DONE":
                            result = item.get("result")
                            text = format_markdown(result) if result is not None else "❌ Error: Empty result"

                            image_hash = item.get("image_hash")
                            cache_version = item.get("cache_version", settings.image_cache_version)
                            user_timezone = item.get("user_timezone", DEFAULT_USER_TIMEZONE)

                            if image_hash and result is not None:
                                try:
                                    await asyncio.to_thread(
                                        image_cache_table.put_item,
                                        Item={
                                            "image_hash": image_hash,
                                            "status": "READY",
                                            "cache_version": int(cache_version),
                                            "result": result,
                                            "created_at": now_iso(),
                                            "updated_at": now_iso(),
                                            "ttl": ttl_epoch(),
                                        },
                                    )
                                except Exception as e:
                                    logger.exception(f"cache put_item failed: {e}")

                            if result is not None:
                                try:
                                    await asyncio.to_thread(
                                        record_meal_for_user,
                                        user_history_table,
                                        int(chat_id),
                                        job_id,
                                        image_hash,
                                        result,
                                        user_timezone,
                                    )
                                except Exception as e:
                                    logger.exception(f"record_meal_for_user failed: {e}")

                        else:
                            text = f"❌ Error: {item.get('error', 'Unknown error')}"

                        await app.bot.send_message(
                            chat_id=int(chat_id),
                            text=text,
                            parse_mode="Markdown",
                        )

                        user_info = ''
                        if user:
                            user_info = f"[{user.get('name')} {user.get('user_id')}]"
                        notification_message = f"DishScan{user_info}:\n<blockquote>{text}</blockquote>"
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