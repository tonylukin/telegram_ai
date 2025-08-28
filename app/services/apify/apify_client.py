import requests

from app.config import APIFY_API_TOKEN
from app.configs.logger import logger


class ApifyClient:
    def _run_apify_actor(self, actor_id: str, payload: dict):
        url = f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items"
        params = {
            "token": APIFY_API_TOKEN,
            "format": "json",
            "clean": "true"
        }
        resp = requests.post(url, params=params, json=payload, timeout=600)
        if resp.status_code >= 300:
            logger.error(f"Apify actor failed with status code: [{resp.status_code}] {resp.text}")
            raise RuntimeError(resp.text)

        return resp.json()