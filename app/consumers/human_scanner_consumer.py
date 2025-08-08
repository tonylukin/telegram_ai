import asyncio
import aio_pika
import aiohttp
import json

from fastapi import HTTPException
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from app.config import RABBITMQ_QUEUE_HUMAN_SCANNER, \
    TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, APP_HOST, API_TOKEN, ENV
from app.configs.logger import logger
from app.consumers.base_consumer import BaseConsumer
from app.bots.human_scanner_ai.translations import translations

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN}"

class HumanScannerConsumer(BaseConsumer):
    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> bool:
        data = json.loads(message.body.decode())
        logger.info(f"📥 Received: {data}")
        chat_id = data['chat_id']
        payload = data['data']
        lang_code = data['lang_code']
        desc = await self._get_desc_from_api(payload, lang_code)

        await self.__send_message(chat_id, desc, lang_code)
        return True

    @staticmethod
    async def __send_message(chat_id: int, text: str, lang_code: str):
        text = text or 'No data'
        keyboard = [
            [InlineKeyboardButton(f"🔄 {translations.get(lang_code).get('start_over')}", callback_data="restart")],
            [InlineKeyboardButton(f"📋 {translations.get(lang_code).get('share')}", switch_inline_query=f"{text}\n\nPowered by @HumanScannerAIBot")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if ENV == 'dev':
            logger.info(f"Sending message to {chat_id}: {text}")
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "reply_markup": reply_markup.to_dict()
                }
            )

    @staticmethod
    async def _get_desc_from_api(payload: dict[str, str], lang_code: str) -> str:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "X-Language-Code": lang_code,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{APP_HOST}/user-info/collect", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    empty_text = translations.get('no_data')
                    if not result["result"]:
                        desc = empty_text
                    else:
                        desc = result["result"].get("description", empty_text)
                        # desc += "\n"
                        # desc += f"Comment count: {result['result'].get('comment_count')}, reaction count: {result['result'].get('reaction_count')}"

                    return desc
                elif resp.status == 400:
                    desc = translations.get('user_not_found')
                    return desc
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error calling API: [{resp.status}] {text}")
                    raise HTTPException(status_code=resp.status, detail=text)

async def main():
    consumer = HumanScannerConsumer(RABBITMQ_QUEUE_HUMAN_SCANNER)
    await consumer.init()

if __name__ == "__main__":
    asyncio.run(main())
