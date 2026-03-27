import asyncio
import json
import os
import re
from datetime import timedelta
from decimal import Decimal

from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key
from telegram.ext import Application

from app.bots.dishscan.date_helpers import (
    now_utc,
    DEFAULT_USER_TIMEZONE,
    now_iso,
    to_local_date,
    ttl_epoch,
)
from app.bots.dishscan.lambda_worker.formatting import format_markdown
from app.configs.logger import logger
from app.services.notification_sender import NotificationSender
from aws_clients import dynamodb, sqs
from config import settings

COMPLETIONS_QUEUE_URL = os.environ["DISHSCAN_COMPLETIONS_QUEUE_URL"]
REFINE_WINDOW_MINUTES = 15

jobs_table = dynamodb.Table(settings.ddb_jobs_table_name)
image_cache_table = dynamodb.Table(settings.ddb_image_cache_table_name)
user_history_table = dynamodb.Table(settings.ddb_user_history_table_name)


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


def set_last_refine_context(
    chat_id: int,
    job_id: str,
    s3_bucket: str,
    s3_key: str,
    image_hash: str,
    user_timezone: str,
    ttl_minutes: int = REFINE_WINDOW_MINUTES,
) -> None:
    now = now_utc()
    expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()

    existing = user_history_table.get_item(
        Key={"pk": f"USER#{chat_id}", "sk": "PROFILE"}
    ).get("Item")

    created_at = existing.get("created_at", now.isoformat()) if existing else now.isoformat()

    user_history_table.put_item(
        Item={
            "pk": f"USER#{chat_id}",
            "sk": "PROFILE",
            "type": "PROFILE",
            "chat_id": int(chat_id),
            "timezone": (existing or {}).get("timezone", DEFAULT_USER_TIMEZONE),
            "created_at": created_at,
            "updated_at": now.isoformat(),
            "last_refine_job_id": job_id,
            "last_refine_s3_bucket": s3_bucket,
            "last_refine_s3_key": s3_key,
            "last_refine_image_hash": image_hash,
            "last_refine_user_timezone": user_timezone,
            "last_refine_expires_at": expires_at,
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


def delete_last_meal_for_user(chat_id: int) -> dict | None:
    meal_item = get_last_meal(chat_id)
    if not meal_item:
        return None

    pk = str(meal_item["pk"])
    sk = str(meal_item["sk"])
    local_date = str(meal_item.get("local_date") or sk.split("#")[1])
    day_sk = f"DAY#{local_date}"

    calories = to_ddb_number(meal_item.get("calories", 0))
    protein = to_ddb_number(meal_item.get("protein_g", 0))
    fat = to_ddb_number(meal_item.get("fat_g", 0))
    carbs = to_ddb_number(meal_item.get("carbs_g", 0))

    day_resp = user_history_table.get_item(
        Key={"pk": f"USER#{chat_id}", "sk": day_sk}
    )
    day_item = day_resp.get("Item")
    if not day_item:
        raise ValueError(f"DAY item not found for chat_id={chat_id}, local_date={local_date}")

    new_total_calories = max(
        to_ddb_number(day_item.get("total_calories", 0)) - calories,
        Decimal("0"),
    )
    new_total_protein = max(
        to_ddb_number(day_item.get("total_protein_g", 0)) - protein,
        Decimal("0"),
    )
    new_total_fat = max(
        to_ddb_number(day_item.get("total_fat_g", 0)) - fat,
        Decimal("0"),
    )
    new_total_carbs = max(
        to_ddb_number(day_item.get("total_carbs_g", 0)) - carbs,
        Decimal("0"),
    )
    new_meals_count = max(
        to_ddb_number(day_item.get("meals_count", 0)) - Decimal("1"),
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
                        job_type = str(item.get("job_type") or "INITIAL").upper()
                        image_hash = item.get("image_hash")
                        cache_version = item.get("cache_version", settings.image_cache_version)
                        user_timezone = item.get("user_timezone", DEFAULT_USER_TIMEZONE)
                        s3_bucket = item.get("s3_bucket")
                        s3_key = item.get("s3_key")

                        if status == "DONE":
                            result = item.get("result")

                            if result is not None:
                                try:
                                    if job_type != "REFINE" and image_hash:
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

                                try:
                                    if job_type == "REFINE":
                                        await asyncio.to_thread(
                                            delete_last_meal_for_user,
                                            int(chat_id),
                                        )

                                    await asyncio.to_thread(
                                        record_meal_for_user,
                                        user_history_table,
                                        int(chat_id),
                                        job_id,
                                        image_hash,
                                        result,
                                        user_timezone,
                                    )

                                    if s3_bucket and s3_key and image_hash:
                                        await asyncio.to_thread(
                                            set_last_refine_context,
                                            int(chat_id),
                                            str(job_id),
                                            str(s3_bucket),
                                            str(s3_key),
                                            str(image_hash),
                                            str(user_timezone),
                                        )
                                except Exception as e:
                                    logger.exception(f"history/refine processing failed: {e}")

                            text = format_markdown(result) if result is not None else "❌ Error: Empty result"

                            if job_type == "REFINE":
                                user_text = "✏️ *Пересчитал с учётом вашего уточнения:*\n\n" + text
                            else:
                                user_text = (
                                    text
                                    + "\n\nЕсли нужно уточнить состав или количество, используйте:\n"
                                    + "`/fix это 2 куска пиццы, соус отдельно, кола 330 мл`"
                                )

                        else:
                            text = f"❌ Error: {item.get('error', 'Unknown error')}"
                            user_text = "Error"

                        await app.bot.send_message(
                            chat_id=int(chat_id),
                            text=user_text,
                            parse_mode="Markdown",
                        )

                        user_info = ""
                        if user:
                            user_info = f" [{user.get('name')} {user.get('user_id')}]"
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