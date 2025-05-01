from telethon.tl.types import Channel
from telethon import TelegramClient
from telethon.tl.functions.contacts import SearchRequest

class ChatSearcher:

    @staticmethod
    async def search_chats(client: TelegramClient, query: str):
        result = await client(SearchRequest(q=query, limit=5))
        results = []
        for chat in result.chats:
            if isinstance(chat, Channel) and chat.megagroup:
                results.append(chat)

        return results
