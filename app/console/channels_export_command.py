import asyncio
import punq
import argparse
import csv
import os

from app.configs.logger import logger
from app.db.session import Session as SQLAlchemySession
from app.services.telegram.channels_api_fetcher import ChannelsApiFetcher
from app.services.telegram.clients_creator import ClientsCreator

async def main():
    container = punq.Container()
    session = SQLAlchemySession()
    container.register(ClientsCreator, instance=ClientsCreator(
        session=session,
    ))
    clients_creator: ClientsCreator = container.resolve(ClientsCreator)
    channels_api_fetcher = ChannelsApiFetcher()
    bot_clients = clients_creator.create_clients_from_bots(limit=1)
    if not bot_clients:
        raise Exception("No bots found")

    bot_client = bot_clients[0]
    await clients_creator.start_client(bot_client, task_name='channels_export')

    try:
        channels = await channels_api_fetcher.get_postable_channels(client=bot_client.client)
        output_dir = os.path.join(os.getcwd(), "data")  # or absolute path like "/home/user/data"
        os.makedirs(output_dir, exist_ok=True)  # create folder if it doesn't exist

        file_path = os.path.join(output_dir, "postable_channels.csv")
        with open(file_path, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            # writer.writerow(["Username", "Title", "Subscribers"])
            for username, title, subscribers in channels:
                writer.writerow([username, title, subscribers])
    except Exception as e:
        logger.error(e)

    await clients_creator.disconnect_client(bot_client)
    session.close()

if __name__ == "__main__":
    asyncio.run(main())

