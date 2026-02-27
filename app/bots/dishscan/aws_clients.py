import boto3
import os
from config import settings

AWS_PROFILE = os.environ.get("AWS_PROFILE", None)

if AWS_PROFILE:
    session = boto3.session.Session(
        profile_name=AWS_PROFILE,
        region_name=settings.aws_region,
    )
else:
    # In Fargate (IAM role from metadata)
    session = boto3.session.Session(
        region_name=settings.aws_region
    )

s3 = session.client("s3")
sqs = session.client("sqs")
events = session.client("events")
dynamodb = session.resource("dynamodb")
