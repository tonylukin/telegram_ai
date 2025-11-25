from fastapi.params import Depends

from app.configs.logger import logger
from app.models.bot import Bot

from app.services.telegram.clients_creator import ClientsCreator
from app.services.telegram.user_messages_search import UserMessagesSearch


class SelfTuningFromChannel:
    def __init__(
            self,
            clients_creator: ClientsCreator = Depends(),
            user_messages_search: UserMessagesSearch = Depends(),
    ):
        self._clients_creator = clients_creator
        self._user_messages_search = user_messages_search

    async def tune(self, channel_name: str, user: str, workflow: str) -> dict[str, int] | None:
        bot_clients = self._clients_creator.create_clients_from_bots(roles=[Bot.ROLE_LEAD_FROM_CHANNEL], limit=1)
        if not bot_clients:
            raise Exception('[SelfTuningFromChannel::tune]: No bots found')

        store = self.__get_rag_store(workflow)
        if not store:
            raise Exception(f'[SelfTuningFromChannel::tune]: No RAG store found for workflow {workflow}')

        try:
            positive_counter = 0
            negative_counter = 0
            await self._clients_creator.start_client(bot_clients[0], task_name='self_tuning_from_channel')

            channel_messages_data = await self._user_messages_search.get_user_messages_like_status_in_channels(bot_client=bot_clients[0], channel_usernames=[channel_name], user=user)
            messages_list = channel_messages_data.get(channel_name)
            if not messages_list:
                logger.info(f"No messages found for user '{user}' in channel '{channel_name}'")
                return None
            for message_data in messages_list:
                if message_data.get('like') is True:
                    if store.add_positive(message_data.get('message')):
                        positive_counter += 1
                if message_data.get('like') is False:
                    if store.add_negative(message_data.get('message')):
                        negative_counter += 1

        except Exception as e:
            logger.error(f"Error during self-tuning: {e}")
            return None
        finally:
            await self._clients_creator.disconnect_client(bot_clients[0])

        return {
            'positive_added': positive_counter,
            'negative_added': negative_counter,
        }

    def __get_rag_store(self, name: str):
        # todo make a service to get workflows by name
        if name == 'hairdresser':
            from app.services.rags.hairdresser.rag_seed_store import RAGSeedStore
            return RAGSeedStore()
        return None