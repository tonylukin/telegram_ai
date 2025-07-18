import os
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

ENV = os.getenv("ENV", "dev")
DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
APP_HOST = os.getenv("APP_HOST")
TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN = os.getenv("TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN")
NEWS_API_ORG_API_KEY = os.getenv("NEWS_API_ORG_API_KEY")
HUGGING_FACE_API_KEY = os.getenv("HUGGING_FACE_API_KEY")
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_QUEUE_HUMAN_SCANNER = os.getenv("RABBITMQ_QUEUE_HUMAN_SCANNER")
API_TOKEN = os.getenv("API_TOKEN")

CONFIG_DIR = Path(__file__).parent / "configs"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "settings.json"
LOCAL_CONFIG_PATH = CONFIG_DIR / "settings.local.json"
with open(DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

# If local exists → override defaults
if LOCAL_CONFIG_PATH.exists():
    with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
        local_config = json.load(f)
    # override only keys that exist in default config
    for k, v in local_config.items():
        if k in config:
            config[k] = v

TELEGRAM_CHANNELS_TO_COMMENT = config['TELEGRAM_CHANNELS_TO_COMMENT']
AI_NEWS_POST_TEXT = config['AI_NEWS_POST_TEXT']
AI_MASS_NEWS_POST_TEXT = config['AI_MASS_NEWS_POST_TEXT']
AI_MASS_NEWS_POST_IMAGE = config['AI_MASS_NEWS_POST_IMAGE']
AI_NEWS_POST_IMAGE = config['AI_NEWS_POST_IMAGE']
AI_NEWS_EMOTIONS = config['AI_NEWS_EMOTIONS']
AI_COMMENT_TEXT = config['AI_COMMENT_TEXT']
AI_COMMENT_TEXT_LINK = config['AI_COMMENT_TEXT_LINK']
AI_USER_INFO_MESSAGES_PROMPT = config['AI_USER_INFO_MESSAGES_PROMPT']
AI_USER_INFO_REACTIONS_PROMPT = config['AI_USER_INFO_REACTIONS_PROMPT']
IMAGE_CREATION_PROBABILITY = config['IMAGE_CREATION_PROBABILITY']
PERSONS = config['PERSONS']
TELEGRAM_CHATS_TO_POST = config['TELEGRAM_CHATS_TO_POST']
TELEGRAM_CHATS_TO_INVITE_FROM = config['TELEGRAM_CHATS_TO_INVITE_FROM']
TELEGRAM_CHATS_TO_INVITE_TO = config['TELEGRAM_CHATS_TO_INVITE_TO']
AI_POST_TEXT_TO_CHANNELS = config['AI_POST_TEXT_TO_CHANNELS']
AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE = config['AI_POST_TEXT_TO_CHANNELS_NO_MESSAGE']
