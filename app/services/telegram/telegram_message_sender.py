import base64
from io import BytesIO

import requests

from app.configs.logger import logger


class TelegramMessageSender:
    def __init__(self, telegram_bot_token: str, telegram_chat_id: str):
        self._telegram_bot_token = telegram_bot_token
        self._telegram_chat_id = telegram_chat_id

    def send_telegram_message(self, message: str, image: str = None) -> bool:
        if image is not None:
            image_data = base64.b64decode(image)
            image_file = BytesIO(image_data)
            url = f"https://api.telegram.org/bot{self._telegram_bot_token}/sendPhoto"
            files = {'photo': image_file}
            data = {'chat_id': self._telegram_chat_id, 'text': message}
            response = requests.post(url, data=data, files=files)
            data = response.json()
            if not data['ok']:
                logger.error(f'[TelegramMessageSender::send_telegram_message] {data}')

        url = f"https://api.telegram.org/bot{self._telegram_bot_token}/sendMessage"
        data = {'chat_id': self._telegram_chat_id, 'text': message, 'parse_mode': 'HTML'}
        response = requests.post(url, data=data)
        data = response.json()
        if not data['ok']:
            logger.error(f'[TelegramMessageSender::send_telegram_message] {data}')

        return bool(data['ok'])

    def set_telegram_bot_token(self, telegram_bot_token: str):
        self._telegram_bot_token = telegram_bot_token
        return self

    def set_telegram_chat_id(self, telegram_chat_id: str):
        self._telegram_chat_id = telegram_chat_id
        return self
