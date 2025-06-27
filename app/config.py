import os
import json
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN = os.getenv("TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN")
NEWS_API_ORG_API_KEY = os.getenv("NEWS_API_ORG_API_KEY")
HUGGING_FACE_API_KEY = os.getenv("HUGGING_FACE_API_KEY")
TELEGRAM_CHANNELS_TO_COMMENT = json.loads(os.getenv("TELEGRAM_CHANNELS_TO_COMMENT", ""))
AI_NEWS_POST_TEXT = os.getenv("AI_NEWS_POST_TEXT")
AI_MASS_NEWS_POST_TEXT = os.getenv("AI_MASS_NEWS_POST_TEXT")
AI_NEWS_POST_IMAGE = os.getenv("AI_NEWS_POST_IMAGE")
AI_COMMENT_TEXT = os.getenv("AI_COMMENT_TEXT")
AI_COMMENT_TEXT_LINK = os.getenv("AI_COMMENT_TEXT_LINK")
AI_USER_INFO_PROMPT = os.getenv("AI_USER_INFO_PROMPT")
IMAGE_CREATION_PROBABILITY = float(os.getenv("IMAGE_CREATION_PROBABILITY", 1))
PERSONS = json.loads(os.getenv("PERSONS", "[]"))
TELEGRAM_CHATS_TO_POST = [s[1:] if s.startswith('@') else s for s in json.loads(os.getenv("TELEGRAM_CHATS_TO_POST", "[]"))] #todo to helper
TELEGRAM_CHATS_TO_INVITE_FROM = [s[1:] if s.startswith('@') else s for s in json.loads(os.getenv("TELEGRAM_CHATS_TO_INVITE_FROM", "[]"))]
TELEGRAM_CHATS_TO_INVITE_TO = json.loads(os.getenv("TELEGRAM_CHATS_TO_INVITE_TO", "[]"))
AI_POST_TEXT_TO_CHANNELS = os.getenv("AI_POST_TEXT_TO_CHANNELS")
