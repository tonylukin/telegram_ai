import json
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from bedrock import estimate_nutrition


DISHSCAN_AWS_REGION = os.environ.get("DISHSCAN_AWS_REGION")
DISHSCAN_DDB_JOBS_TABLE_NAME = os.environ["DISHSCAN_DDB_JOBS_TABLE_NAME"]

session = boto3.session.Session(region_name=DISHSCAN_AWS_REGION)
s3 = session.client("s3")
dynamodb = session.resource("dynamodb")
jobs_table = dynamodb.Table(DISHSCAN_DDB_JOBS_TABLE_NAME)
events = session.client("events")

DISHSCAN_EVENT_BUS_NAME = os.environ["DISHSCAN_EVENT_BUS_NAME"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def to_dynamodb_compatible(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamodb_compatible(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamodb_compatible(v) for v in value]
    return value


def handler(event, context):
    # Process SQS batch
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        job_id = body["job_id"]
        # chat_id = int(body["chat_id"])
        bucket = body["s3_bucket"]
        key = body["s3_key"]

        try:
            # Mark job as PROCESSING
            jobs_table.update_item(
                Key={"pk": f"JOB#{job_id}", "sk": "META"},
                UpdateExpression="SET #s = :s, updated_at = :u",
                ExpressionAttributeNames={
                    "#s": "status",
                },
                ExpressionAttributeValues={
                    ":s": "PROCESSING",
                    ":u": now_iso(),
                },
            )

            # Fetch image from S3
            obj = s3.get_object(Bucket=bucket, Key=key)
            image_bytes = obj["Body"].read()

            # Call Bedrock to estimate nutrition
            result = estimate_nutrition(image_bytes)

            result_ddb = to_dynamodb_compatible(result)

            # Save final result (avoid reserved keyword issues)
            jobs_table.update_item(
                Key={"pk": f"JOB#{job_id}", "sk": "META"},
                UpdateExpression="SET #s = :s, updated_at = :u, #res = :r",
                ExpressionAttributeNames={
                    "#s": "status",
                    "#res": "result",
                },
                ExpressionAttributeValues={
                    ":s": "DONE",
                    ":u": now_iso(),
                    ":r": result_ddb,
                },
            )

            events.put_events(
                Entries=[{
                    "EventBusName": DISHSCAN_EVENT_BUS_NAME,
                    "Source": "dishscan.worker",
                    "DetailType": "dishscan.job.completed",
                    "Detail": json.dumps({
                        "job_id": job_id,
                        "status": "DONE",
                    }),
                }]
            )

        except Exception as e:
            # Mark job as FAILED (error is reserved word -> alias it)
            jobs_table.update_item(
                Key={"pk": f"JOB#{job_id}", "sk": "META"},
                UpdateExpression="SET #s = :s, updated_at = :u, #err = :err",
                ExpressionAttributeNames={
                    "#s": "status",
                    "#err": "error",
                },
                ExpressionAttributeValues={
                    ":s": "FAILED",
                    ":u": now_iso(),
                    ":err": str(e),
                },
            )

            events.put_events(
                Entries=[{
                    "EventBusName": DISHSCAN_EVENT_BUS_NAME,
                    "Source": "dishscan.worker",
                    "DetailType": "dishscan.job.completed",
                    "Detail": json.dumps({
                        "job_id": job_id,
                        "status": "FAILED",
                    }),
                }]
            )

            # Let SQS retry / move to DLQ
            raise
