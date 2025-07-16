import asyncio
import aio_pika
import aiohttp
import json

from fastapi import HTTPException

from app.config import RABBITMQ_QUEUE_HUMAN_SCANNER, \
    TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN, APP_HOST, API_TOKEN
from app.configs.logger import logger
from app.consumers.base_consumer import BaseConsumer

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_HUMAN_SCANNER_AI_BOT_TOKEN}"

class HumanScannerConsumer(BaseConsumer):
    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage):
        data = json.loads(message.body.decode())
        logger.info(f"📥 Received: {data}")
        chat_id = data['chat_id']
        payload = data['data']
        desc = await self.__get_desc_from_api(payload)

        await self.__send_message(chat_id, desc)

    @staticmethod
    async def __send_message(chat_id: int, text: str):
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{TELEGRAM_API}/sendMessage",
                json={"chat_id": chat_id, "text": text}
            )

    @staticmethod
    async def __get_desc_from_api(payload: dict[str, str]) -> str | None:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{APP_HOST}/user-info/collect", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    desc = result["result"].get("description", "Нет описания.")
                    return desc
                elif resp.status == 400:
                    desc = 'User not found'
                    return desc
                else:
                    text = await resp.text()
                    logger.error(f"❌ Error calling API: [{resp.status}] {text}")
                    raise HTTPException(status_code=resp.status, detail=text)

async def main():
    consumer = HumanScannerConsumer(RABBITMQ_QUEUE_HUMAN_SCANNER)
    await consumer.init()

asyncio.run(main())
