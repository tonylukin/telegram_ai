from fastapi.params import Depends
from telethon import TelegramClient
import asyncio

from telethon.tl.functions.messages import GetDiscussionMessageRequest

from app.configs.logger import logging
from app.db.queries.bot import get_bot
from app.db.queries.tg_user_invited import get_invited_users
from app.db.session import Session
from app.models.tg_user_invited import TgUserInvited
from app.services.telegram.clients_creator import ClientsCreator, \
    get_telegram_clients_to_invite
import random
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, User, PeerChannel


class UserInviter:
    MAX_USERS = 10
    DELAY_RANGE = (10, 20)

    def __init__(self, clients_creator: ClientsCreator = Depends(get_telegram_clients_to_invite)):
        self.clients_creator = clients_creator
        self.clients = []
        self.invitedUsers = set()
        self.session = Session()
        self.source_channel = '@pravdadirty'
        self.target_channel = '@news_luxury_narrator'

    async def invite_users_from_comments(self) -> list[dict[str, int]]:
        clients = await self.clients_creator.create_clients()

        return await asyncio.gather(
            *(self.__start_client(client) for client in clients)
        )

    async def __start_client(self, client: TelegramClient) -> dict[str, int]:
        await client.start()
        logging.info(f"{client.session.filename} started")

        bot = get_bot(client)
        if bot is None:
            logging.error('Bot not found')
            return {}

        invited = 0
        me = await client.get_me()
        messages = await client.get_messages(self.source_channel, limit=self.MAX_USERS * 3)
        logging.info(f"Logged in as {me.username or me.id}")

        for msg in messages:
            if not msg.replies:
                continue
            try:
                discussion = await client(GetDiscussionMessageRequest(
                    peer=self.source_channel,
                    msg_id=msg.id
                ))
                discussion_channel_id = discussion.messages[0].peer_id.channel_id
                discussion_peer = PeerChannel(discussion_channel_id)
                comments = await client.get_messages(discussion_peer, limit=self.MAX_USERS * 4)

                for comment in comments:
                    user = await client.get_entity(comment.sender_id)
                    invited_user = get_invited_users(tg_user_id=user.id, channel=self.target_channel)
                    if user.is_self or user.bot or invited >= self.MAX_USERS or user.id in self.invitedUsers or invited_user is not None:
                        continue
                    self.invitedUsers.add(user.id)

                    try:
                        await client(InviteToChannelRequest(
                            channel=self.target_channel,
                            users=[user]
                        ))
                        logging.info(f"✅ Invited {user.username or user.id}")
                        invited += 1
                    except Exception as e:
                        logging.error(f"❌ Could not invite {user.username or user.id}: {e}")

                    tg_user_invited = TgUserInvited(
                        tg_user_id=user.id,
                        tg_username=user.username,
                        channel=self.target_channel,
                    )
                    self.session.add(tg_user_invited)
                    await asyncio.sleep(random.randint(*self.DELAY_RANGE))

            except Exception as e:
                logging.error(f"⚠️ Error getting discussion: {e}")

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        finally:
            self.session.close()

        await client.disconnect()
        return {client.session.filename: invited}
