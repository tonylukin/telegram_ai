from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, TELEGRAM_NOTIFICATIONS_CHAT_ID
from app.services.telegram.telegram_message_sender import TelegramMessageSender


class NotificationSender:
    def __init__(self):
        self._telegram_message_sender = TelegramMessageSender(TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, TELEGRAM_NOTIFICATIONS_CHAT_ID)

    async def send_notification_message(self, message: str):
        self._telegram_message_sender.send_telegram_message(message)
