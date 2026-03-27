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
    for record in event.get("Records", []):
        body = json.loads(record["body"])

        job_id = body["job_id"]
        bucket = body["s3_bucket"]
        key = body["s3_key"]
        job_type = str(body.get("job_type") or "INITIAL").upper()
        clarification_text = (body.get("clarification_text") or "").strip()
        parent_job_id = body.get("parent_job_id")

        try:
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

            obj = s3.get_object(Bucket=bucket, Key=key)
            image_bytes = obj["Body"].read()

            result = estimate_nutrition(
                image_bytes,
                clarification_text=clarification_text if job_type == "REFINE" else None,
            )

            result_ddb = to_dynamodb_compatible(result)

            jobs_table.update_item(
                Key={"pk": f"JOB#{job_id}", "sk": "META"},
                UpdateExpression="""
                    SET #s = :s,
                        updated_at = :u,
                        #res = :r,
                        job_type = :job_type,
                        clarification_text = :clarification_text,
                        parent_job_id = :parent_job_id
                """,
                ExpressionAttributeNames={
                    "#s": "status",
                    "#res": "result",
                },
                ExpressionAttributeValues={
                    ":s": "DONE",
                    ":u": now_iso(),
                    ":r": result_ddb,
                    ":job_type": job_type,
                    ":clarification_text": clarification_text,
                    ":parent_job_id": parent_job_id,
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
                        "job_type": job_type,
                    }),
                }]
            )

        except Exception as e:
            jobs_table.update_item(
                Key={"pk": f"JOB#{job_id}", "sk": "META"},
                UpdateExpression="""
                    SET #s = :s,
                        updated_at = :u,
                        #err = :err,
                        job_type = :job_type,
                        clarification_text = :clarification_text,
                        parent_job_id = :parent_job_id
                """,
                ExpressionAttributeNames={
                    "#s": "status",
                    "#err": "error",
                },
                ExpressionAttributeValues={
                    ":s": "FAILED",
                    ":u": now_iso(),
                    ":err": str(e),
                    ":job_type": job_type,
                    ":clarification_text": clarification_text,
                    ":parent_job_id": parent_job_id,
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
                        "job_type": job_type,
                    }),
                }]
            )

            raise