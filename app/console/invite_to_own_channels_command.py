import asyncio
import punq
import argparse

from telethon import TelegramClient, functions
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch

from app.config import OWN_CHANNELS
from app.configs.logger import logger
from app.models.bot import Bot
from app.services.telegram.helpers import promote_user, join_chats
from app.services.telegram.clients_creator import ClientsCreator, BotClient
from app.db.session import Session as SQLAlchemySession

async def resolve_user_from_group(client: TelegramClient, group_name: str, user_id: int):
    result = await client(GetParticipantsRequest(
        channel=group_name,
        filter=ChannelParticipantsSearch(""),  # empty string = get all
        offset=0,
        limit=200,
        hash=0
    ))

    for user in result.users:
        if user.id == user_id:
            return user  # This is a valid User entity usable by this client

    raise Exception(f"User {user_id} not found in group {group_name}")

async def promote_users(clients_creator: ClientsCreator, super_admin_bot_client: BotClient, promoting_bot_client: BotClient, group_username: str, bio: str | None) -> bool:
    logger.info(f"Start promoting for {group_username} by {super_admin_bot_client.get_name()}")
    try:
        await clients_creator.start_client(super_admin_bot_client, 'promote_user_super_admin')
        super_admin_bot = await super_admin_bot_client.client.get_me()
        await clients_creator.start_client(promoting_bot_client, 'promote_user')
        promoting_bot = await promoting_bot_client.client.get_me()

        if bio:
            logger.info(f"Setting bio to {bio}")
            await promoting_bot_client.client(functions.account.UpdateProfileRequest(about=bio))

        if super_admin_bot.id == promoting_bot.id:
            logger.info(f"Skip admin self admin #{super_admin_bot.id} and a candidate {promoting_bot.id}")
            return False

        try:
            logger.info(f"Joining {group_username} by #{promoting_bot_client.get_name()}")
            await join_chats(promoting_bot_client.client, [group_username])

            logger.info(f"Promoting #{promoting_bot.id} as admin for {group_username} by #{super_admin_bot.id}")
            candidate = await resolve_user_from_group(super_admin_bot_client.client, group_username, promoting_bot.id)
            await promote_user(super_admin_bot_client.client, candidate, group_username)
        except Exception as e:
            logger.error(e)
            return False

        return True
    except Exception as e:
        logger.error(e)
        return False
    finally:
        await clients_creator.disconnect_client(super_admin_bot_client)
        await clients_creator.disconnect_client(promoting_bot_client)

async def main():
    BATCH_SIZE = 5
    parser = argparse.ArgumentParser()
    parser.add_argument("--set_bio", help="Set bio to all bots for promoting", required=False)
    args = parser.parse_args()

    container = punq.Container()
    session = SQLAlchemySession()
    container.register(ClientsCreator, instance=ClientsCreator(
        session=session,
    ))
    clients_creator: ClientsCreator = container.resolve(ClientsCreator)
    super_admin_bot_clients = clients_creator.create_clients_from_bots(roles=[Bot.ROLE_SUPER_ADMIN], limit=1)
    if not super_admin_bot_clients:
        session.close()
        raise Exception("No client found")

    page = 0
    while True:
        offset = page * BATCH_SIZE
        bot_clients = clients_creator.create_clients_from_bots(limit=BATCH_SIZE, offset=offset)

        for channel in OWN_CHANNELS:
            for bot_client in bot_clients:
                try:
                    result = await promote_users(clients_creator, super_admin_bot_clients[0], bot_client, channel, args.set_bio)
                    logger.info(f"Success: {result}")
                except Exception as e:
                    logger.error(e)
        page += 1
        if len(bot_clients) < BATCH_SIZE:
            break

    session.close()


if __name__ == "__main__":
    asyncio.run(main())
