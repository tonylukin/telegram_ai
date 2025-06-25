from telethon import TelegramClient, functions, types
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel


class ChatSearcher:

    @staticmethod
    async def search_chats(client: TelegramClient, query: str):
        result = await client(SearchRequest(q=query, limit=5))
        results = [await client.get_entity(query)]
        for chat in result.chats:
            if isinstance(chat, Channel) and chat.megagroup:
                results.append(chat)

        return results

    @staticmethod
    async def search_in_posts_by_hashtag(client: TelegramClient, query: str):
        result = await client(functions.channels.SearchPostsRequest(
            hashtag=query,
            offset_rate=0,
            offset_peer=types.InputPeerEmpty(),
            offset_id=0,
            limit=5
        ))
        results = []
        for post in result.messages:
            if isinstance(post.peer_id, types.PeerChannel):
                channel = await client.get_entity(post.peer_id)
                if isinstance(channel, types.Channel) and channel.megagroup:
                    results.append(channel)

        return results
