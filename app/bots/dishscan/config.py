import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    # Telegram
    telegram_bot_token: str = os.environ["TF_VAR_TELEGRAM_DISHSCAN_BOT_TOKEN"]

    # AWS
    aws_region: str = os.environ["DISHSCAN_AWS_REGION"]
    s3_bucket: str = os.environ["DISHSCAN_S3_BUCKET"]
    sqs_queue_url: str = os.environ["DISHSCAN_SQS_QUEUE_URL"]
    event_bus_name: str = os.environ["DISHSCAN_EVENT_BUS_NAME"]
    ddb_table_name: str = os.environ["DISHSCAN_DDB_TABLE_NAME"]

settings = Settings()
