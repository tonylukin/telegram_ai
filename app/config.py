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
TELEGRAM_CHANNELS_TO_COMMENT = json.loads(os.getenv("TELEGRAM_CHANNELS_TO_COMMENT", ""))
TELEGRAM_USERS_TO_COMMENT = json.loads(os.getenv("TELEGRAM_USERS_TO_COMMENT", "[]"))
TELEGRAM_USERS_TO_REACT = json.loads(os.getenv("TELEGRAM_USERS_TO_REACT", "[]"))
AI_NEWS_POST_TEXT = os.getenv("AI_NEWS_POST_TEXT")
AI_NEWS_POST_IMAGE = os.getenv("AI_NEWS_POST_IMAGE")
AI_COMMENT_TEXT = os.getenv("AI_COMMENT_TEXT")
AI_COMMENT_TEXT_LINK = os.getenv("AI_COMMENT_TEXT_LINK")
IMAGE_CREATION_PROBABILITY = float(os.getenv("IMAGE_CREATION_PROBABILITY", 1))
PERSONS = json.loads(os.getenv("PERSONS", "[]"))
TELEGRAM_CHATS_TO_POST = [s[1:] if s.startswith('@') else s for s in json.loads(os.getenv("TELEGRAM_CHATS_TO_POST", "[]"))]
AI_POST_TEXT_TO_CHANNELS = os.getenv("AI_POST_TEXT_TO_CHANNELS")
