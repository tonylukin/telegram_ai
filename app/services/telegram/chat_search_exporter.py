import os
import csv

from fastapi.params import Depends

from app.config import EXPORT_CHANNELS_PREDEFINED_QUERIES, CHAT_MESSENGER_DEFAULT_CHANNELS_LIST_CSV_PATH
from app.configs.logger import logger
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator


class ChatSearchExporter:
    def __init__(
        self,
        chat_searcher: ChatSearcher = Depends(),
        clients_creator: ClientsCreator = Depends()
    ):
        self._chat_searcher = chat_searcher
        self._clients_creator = clients_creator

    async def export(self, queries: list[str] = None) -> list[tuple[str, str, int]]:
        bot_clients = self._clients_creator.create_clients_from_bots(limit=1)
        if not bot_clients:
            raise Exception("No bots found")

        bot_client = bot_clients[0]
        await self._clients_creator.start_client(bot_client, task_name='chat_search_export')

        if queries is None:
            queries = EXPORT_CHANNELS_PREDEFINED_QUERIES
        channels_found: list[tuple[str, str, int]] = []
        for query in queries:
            try:
                query_channels_found = await self._chat_searcher.search_chats(bot_client.client, query)
                if not query_channels_found:
                    logger.info(f"No channels found for {query}")
                    continue

                for channel in query_channels_found:
                    if channel.username and 1000 <= channel.participants_count <= 10000 and not channel.broadcast:
                        channels_found.append(('@' + channel.username, channel.title, channel.participants_count))

            except Exception as e:
                logger.error(f"⚠️ Error on {query}: {e}")

        try:
            output_dir = os.path.join(os.getcwd(), "data")  # or absolute path like "/home/user/data"
            os.makedirs(output_dir, exist_ok=True)  # create folder if it doesn't exist

            # file_path = os.path.join(output_dir, f"chat_search_exporter_found_channels_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            file_path = os.path.join(output_dir, f"{CHAT_MESSENGER_DEFAULT_CHANNELS_LIST_CSV_PATH.lstrip('data/')}")
            with open(file_path, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                for username, title, subscribers in channels_found:
                    writer.writerow([username, title, subscribers])
        except Exception as e:
            logger.error(e)

        return channels_found
