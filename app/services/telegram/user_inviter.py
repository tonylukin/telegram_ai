import asyncio
import random

from fastapi.params import Depends
from telethon.tl.functions.channels import InviteToChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import GetDiscussionMessageRequest
from telethon.tl.types import PeerChannel

from app.config import TELEGRAM_CHATS_TO_INVITE_FROM, TELEGRAM_CHATS_TO_INVITE_TO
from app.configs.logger import logging, logger
from app.db.queries.tg_user_invited import get_invited_users
from app.db.session import Session
from app.dependencies import get_db
from app.models.tg_user_invited import TgUserInvited
from app.services.telegram.clients_creator import ClientsCreator, \
    get_bot_roles_to_invite, BotClient
from app.services.telegram.helpers import join_chats, get_chat_from_channel


class UserInviter:
    MAX_USERS = 20
    DELAY_RANGE = (10, 20)

    def __init__(self, clients_creator: ClientsCreator = Depends(), session: Session = Depends(get_db)):
        self.clients_creator = clients_creator
        self.clients = []
        self.invitedUsers = set()
        self.session = session
        self.source_channels = TELEGRAM_CHATS_TO_INVITE_FROM #todo pass to constructor in future
        self.target_channels = TELEGRAM_CHATS_TO_INVITE_TO

    async def invite_users_from_comments(self, count: int = None) -> list[dict[str, int]]:
        bot_clients = self.clients_creator.create_clients_from_bots(roles=get_bot_roles_to_invite())
        if count is None:
            count = UserInviter.MAX_USERS

        return await asyncio.gather(
            *(self.__start_client(client, self.source_channels, self.target_channels, count) for client in bot_clients)
        )

    async def __start_client(self, bot_client: BotClient, channels: list[str], target_channels: list[str], count: int) -> dict[str, int]:
        client = bot_client.client
        await client.start()
        logging.info(f"{bot_client.get_name()} started")

        bot = bot_client.bot
        random.shuffle(channels)
        await join_chats(client, channels)

        target_channel = random.choice(target_channels)
        if not target_channel:
            logger.error('No target channel')
            return {}

        invited = 0
        messages_by_channel = {}
        channel_entities = {}
        for channel in channels:
            try:
                channel_entity = await client.get_entity(channel)
                linked_chat_id = await get_chat_from_channel(client, channel_entity)
                if linked_chat_id is None:
                    continue
                if isinstance(linked_chat_id, int):
                    try:
                        messages_by_channel[channel] = await client.get_messages(PeerChannel(linked_chat_id), limit=count)
                    except Exception as e:
                        logger.error(f"Error {channel} [{linked_chat_id}]: {e}")
                        continue
                    channel_entities[channel] = await client.get_entity(linked_chat_id)
                else:
                    messages_by_channel[channel] = await client.get_messages(channel, limit=count)
                    channel_entities[channel] = channel_entity
            except Exception as e:
                logging.error(f"⚠️ Error getting channel messages: {e}")

        for channel, messages in messages_by_channel.items():
            for msg in messages:
                if not msg.replies or channel_entities[channel] is None:
                    continue
                try:
                    discussion = await client(GetDiscussionMessageRequest(
                        peer=channel_entities[channel],
                        msg_id=msg.id
                    ))
                    discussion_channel_id = discussion.messages[0].peer_id.channel_id
                    discussion_peer = PeerChannel(discussion_channel_id)
                    comments = await client.get_messages(discussion_peer, limit=count)

                    for comment in comments:
                        user = await client.get_entity(comment.sender_id)
                        invited_user = get_invited_users(self.session, tg_user_id=user.id, channel=target_channel)
                        if user.is_self or user.bot or invited >= count or user.id in self.invitedUsers or invited_user is not None:
                            continue
                        self.invitedUsers.add(user.id)

                        try:
                            await asyncio.sleep(random.randint(*self.DELAY_RANGE))
                            await client(InviteToChannelRequest(
                                channel=target_channel,
                                users=[user]
                            ))
                            logging.info(f"✅ Invited {user.username or user.id}")
                            invited += 1
                        except Exception as e:
                            logging.error(f"❌ Could not invite {user.username or user.id}[{channel}][{bot.name}]: {e}")
                            continue

                        tg_user_invited = TgUserInvited(
                            tg_user_id=user.id,
                            tg_username=user.username,
                            channel=target_channel,
                            channel_from=channel,
                            bot_id=bot.id,
                        )
                        self.session.add(tg_user_invited)

                except Exception as e:
                    logging.error(f"⚠️ Error getting discussion: {e}")

        await client.disconnect()

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logging.error(e)
        finally:
            self.session.close()

        return {bot_client.get_name(): invited}
