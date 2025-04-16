import os
import json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
NEWS_API_ORG_API_KEY = os.getenv("NEWS_API_ORG_API_KEY")
HUGGING_FACE_API_KEY = os.getenv("HUGGING_FACE_API_KEY")
# TELEGRAM_CHANNELS_TO_COMMENT = os.getenv("TELEGRAM_CHANNELS_TO_COMMENT", "").split(",")
TELEGRAM_CHANNELS_TO_COMMENT = json.loads(os.getenv("TELEGRAM_CHANNELS_TO_COMMENT", ""))
TELEGRAM_USERS_TO_COMMENT = json.loads(os.getenv("TELEGRAM_USERS_TO_COMMENT", "[]"))
