import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # AWS
    aws_region: str = os.environ["DISHSCAN_AWS_REGION"]
    s3_bucket: str = os.environ["DISHSCAN_S3_BUCKET"]
    sqs_queue_url: str = os.environ["DISHSCAN_SQS_QUEUE_URL"]
    event_bus_name: str = os.environ["DISHSCAN_EVENT_BUS_NAME"]
    ddb_jobs_table_name: str = 'dishscan-jobs'
    ddb_user_history_table_name: str = 'dishscan-user-history'
    ddb_image_cache_table_name: str = 'dishscan-image-cache'
    image_cache_version: int = 1

settings = Settings()
