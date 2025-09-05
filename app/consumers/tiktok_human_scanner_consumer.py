import asyncio
import aiohttp

from fastapi import HTTPException

from app.config import \
    APP_HOST, API_TOKEN, RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER
from app.configs.logger import logger
from app.bots.human_scanner_ai.translations import translations
from app.consumers.human_scanner_consumer import HumanScannerConsumer
from app.services.notification_sender import NotificationSender


class TikTokHumanScannerConsumer(HumanScannerConsumer):

    async def _get_desc_from_api(self, payload: dict[str, str], lang_code: str) -> str:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "X-Language-Code": lang_code,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{APP_HOST}/user-info/tiktok-collect", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    empty_text = translations.get('no_data')
                    if not result["result"]:
                        desc = empty_text
                    else:
                        desc = result["result"].get("description", empty_text)

                    return desc
                elif resp.status == 400:
                    desc = translations.get('user_not_found')
                    return desc
                else:
                    text = await resp.text()
                    message = f"❌ Error calling API: [{resp.status}] {text}"
                    logger.error(message)
                    await self._notification_sender.send_notification_message(message)
                    raise HTTPException(status_code=resp.status, detail=text)

    def get_notification_message(self) -> str | None:
        if self.output_data is None:
            return None

        payload: dict = self.output_data.get("payload")
        return f"[TikTok] Username: {payload['username']}\nDescription: {self.output_data.get('desc')}"

async def main():
    consumer = TikTokHumanScannerConsumer(queue=RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER, notification_sender=NotificationSender())
    await consumer.init()

if __name__ == "__main__":
    asyncio.run(main())
