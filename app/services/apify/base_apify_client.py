from apify_client import ApifyClient as SdkApifyClient
from app.configs.logger import logger
from app.config import APIFY_API_TOKEN


class BaseApifyClient:
    def __init__(self, api_token: str | None = None):
        self.api_token = api_token or APIFY_API_TOKEN
        if not self.api_token:
            logger.error("Apify API token not provided!")
            raise ValueError("You must provide an Apify API token or set the environment variable APIFY_API_TOKEN.")

        self.client = SdkApifyClient(self.api_token)

    def _run_apify_actor(self, actor_id: str, payload: dict) -> list[dict] | None:
        """
        Runs an Apify actor, waits for it to finish, and returns the results.

        :param actor_id: ID of the actor (e.g., 'apify/instagram-profile-scraper').
        :param payload: Input data for the actor (run input).
        :return: A list of dictionaries with results, or None in case of an error.
        """
        logger.info(f"Running Apify actor '{actor_id}'...")
        try:
            actor_client = self.client.actor(actor_id)
            run_info = actor_client.call(run_input=payload)

            if not run_info or 'status' not in run_info:
                logger.error(f"Failed to get run info for actor '{actor_id}'.")
                return None

            logger.info(f"Actor '{actor_id}' finished with status: {run_info['status']}")

            if run_info['status'] != 'SUCCEEDED':
                logger.error(f"Actor '{actor_id}' did not complete successfully. Run details: {run_info}")
                return None

            dataset_client = self.client.dataset(run_info['defaultDatasetId'])
            items = dataset_client.list_items().items

            results = list(items)

            logger.info(f"Retrieved {len(results)} items from actor '{actor_id}'.")
            return results

        except Exception as e:
            logger.error(f"Error occurred while running actor '{actor_id}': {e}", exc_info=True)
            return None
