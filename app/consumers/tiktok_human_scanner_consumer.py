import asyncio
import aiohttp

from fastapi import HTTPException

from app.config import \
    APP_HOST, API_TOKEN, RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER
from app.configs.logger import logger
from app.bots.human_scanner_ai.translations import translations
from app.consumers.human_scanner_consumer import HumanScannerConsumer


class TikTokHumanScannerConsumer(HumanScannerConsumer):

    @staticmethod
    async def _get_desc_from_api(payload: dict[str, str], lang_code: str) -> str:
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
                    logger.error(f"❌ Error calling API: [{resp.status}] {text}")
                    raise HTTPException(status_code=resp.status, detail=text)

async def main():
    consumer = TikTokHumanScannerConsumer(RABBITMQ_QUEUE_TIKTOK_HUMAN_SCANNER)
    await consumer.init()

if __name__ == "__main__":
    asyncio.run(main())
