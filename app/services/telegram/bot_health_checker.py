from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import TG_TEST_GROUP
from app.configs.logger import logger
from app.dependencies import get_db
from app.models.bot import Bot
from app.services.telegram.clients_creator import ClientsCreator
from telethon.errors import RPCError, AuthKeyUnregisteredError, UserDeactivatedBanError, UserDeactivatedError, \
    ChatWriteForbiddenError, UserBannedInChannelError, FloodWaitError, ChatAdminRequiredError

from app.services.telegram.helpers import join_chats


class BotHealthChecker:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            session: Session = Depends(get_db)
    ):
        self._clients_creator = clients_creator
        self._session = session

    async def check_bots_statuses(self) -> dict[str, str]:
        bot_clients = self._clients_creator.create_clients_from_bots()
        results = {}
        for bot_client in bot_clients:
            client = bot_client.client
            result = 'active'

            try:
                await self._clients_creator.start_client(bot_client)
                me = await client.get_me()
                await client.send_message(me, "Test message (ignore) ✅")
                await join_chats(client, [TG_TEST_GROUP])
                await client.send_message(await client.get_entity(TG_TEST_GROUP), "Test message (ignore) ✅")

            except ChatWriteForbiddenError:
                logger.error("❌ Cannot send messages: ChatWriteForbiddenError (likely muted/restricted).")
                result = 'ChatWriteForbiddenError'

            except UserBannedInChannelError:
                logger.error("❌ Cannot send messages: banned in channel.")
                result = 'UserBannedInChannelError'
                if Bot.ROLE_POST in bot_client.bot.roles:
                    bot_client.bot.roles.remove(Bot.ROLE_POST)

            except FloodWaitError as e:
                logger.error(f"⚠️ Flood wait: must wait {e.seconds} seconds before sending.")
                result = 'FloodWaitError'

            except AuthKeyUnregisteredError:
                logger.error("❌ Session is invalid or logged out (AuthKeyUnregisteredError).")
                result = "invalid_session"

            except UserDeactivatedBanError:
                logger.error("❌ Account is banned (UserDeactivatedBanError).")
                result = "banned"

            except UserDeactivatedError:
                logger.error("❌ Account is deactivated (UserDeactivatedError).")
                result = "deactivated"

            except RPCError as e:
                if "FROZEN_METHOD_INVALID" in str(e):
                    logger.error("⚠️ Account is frozen (FROZEN_METHOD_INVALID).")
                    result = "frozen"
                else:
                    logger.error(f"⚠️ RPCError: {e}")
                    result = "rpc_error [frozen]"
                bot_client.bot.roles = []

            except ChatAdminRequiredError:
                logger.error(f"❌ Cannot send messages: admin required.")
                result = "ChatAdminRequiredError"

            except Exception as e:
                logger.error(f"⚠️ Unknown error: {e}")
                result = "unknown"

            finally:
                await self._clients_creator.disconnect_client(bot_client)

            results[bot_client.get_name()] = result

        return results
