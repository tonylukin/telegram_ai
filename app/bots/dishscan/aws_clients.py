import boto3
from config import settings

# Note: Prefer IAM Role credentials (no static access keys in env).
session = boto3.session.Session(region_name=settings.aws_region)

s3 = session.client("s3")
sqs = session.client("sqs")
events = session.client("events")
dynamodb = session.resource("dynamodb")