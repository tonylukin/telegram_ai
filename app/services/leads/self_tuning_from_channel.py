import re
from fastapi.params import Depends
import json
from pathlib import Path

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
                    if store.add_positive(self.__sanitize_text(message_data.get('message'))):
                        positive_counter += 1
                if message_data.get('like') is False:
                    if store.add_negative(self.__sanitize_text(message_data.get('message'))):
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

    async def create_ml_data(self, channel_name: str, user: str, workflow: str) -> dict[str, int] | None:
        bot_clients = self._clients_creator.create_clients_from_bots(roles=[Bot.ROLE_LEAD_FROM_CHANNEL], limit=1)
        if not bot_clients:
            raise Exception('[SelfTuningFromChannel::create_ml_data]: No bots found')

        try:
            positive_counter = 0
            negative_counter = 0
            await self._clients_creator.start_client(bot_clients[0], task_name='create_ml_data_from_channel')

            channel_messages_data = await self._user_messages_search.get_user_messages_like_status_in_channels(bot_client=bot_clients[0], channel_usernames=[channel_name], user=user, limit=100)
            messages_list = channel_messages_data.get(channel_name)
            if not messages_list:
                logger.info(f"No messages found for user '{user}' in channel '{channel_name}'")
                return None

            dataset_dir = Path('data/ml')
            dataset_dir.mkdir(parents=True, exist_ok=True)
            filename = f'training_dataset_{workflow}.jsonl'
            dataset_file = dataset_dir / filename
            # load existing entries to avoid duplicates
            existing_entries = set()
            if dataset_file.exists():
                with dataset_file.open('r', encoding='utf-8') as rf:
                    for line in rf:
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        text = (obj.get('text') or '').strip()
                        label = obj.get('label')
                        if text and label in (0, 1):
                            existing_entries.add((text, label))

            seen = set()
            with dataset_file.open('a', encoding='utf-8') as f:
                for message_data in messages_list:
                    like = message_data.get('like')
                    if like is True or like is False:
                        text = self.__sanitize_text(message_data.get('message') or '').strip()
                        if text in seen:
                            continue
                        seen.add(text)
                        label = 1 if like is True else 0
                        key = (text, label)
                        if not text or key in existing_entries:
                            continue
                        f.write(json.dumps({"text": text, "label": label}, ensure_ascii=False) + '\n')
                        existing_entries.add(key)
                        if like is True:
                            positive_counter += 1
                        else:
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

    def __sanitize_text(self, text: str) -> str:
        sanitized_text = re.search(r'^Found new lead.*?\]\s*(.*?)\s*(\[\d+,[^\]]*\])*\s*$', text, re.S)
        return sanitized_text.group(1) if sanitized_text else text
