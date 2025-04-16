import base64
from io import BytesIO
from app.configs.logger import logging

import requests
from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message: str, image: str) -> bool:
    if image is not None:
        image_data = base64.b64decode(image)
        image_file = BytesIO(image_data)
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        files = {'photo': image_file}
        data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
        response = requests.post(url, data=data, files=files)
        data = response.json()
        if not data['ok']:
            logging.error(data)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    response = requests.post(url, data=data)
    data = response.json()
    if not data['ok']:
        logging.error(data)

    return bool(data['ok'])
