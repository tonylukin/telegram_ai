from app.config import TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, TELEGRAM_NOTIFICATIONS_CHAT_ID
from app.services.telegram.telegram_message_sender import TelegramMessageSender


# todo should be implemented with abstract class instead of TG implementation
class NotificationSender:
    telegram_message_sender: TelegramMessageSender

    def __init__(self, bot_token: str = TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, chat_id: str = TELEGRAM_NOTIFICATIONS_CHAT_ID):
        self.telegram_message_sender = TelegramMessageSender(bot_token, chat_id)

    async def send_notification_message(self, message: str):
        self.telegram_message_sender.send_telegram_message(message)
