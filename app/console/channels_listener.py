import asyncio
import punq

from app.config import TELEGRAM_USERS_TO_COMMENT
from app.services.ai.gemini_client import GeminiClient
from app.services.telegram.channel_message_sender import ChannelMessageSender
from app.services.telegram.clients_creator import ClientsCreator

if __name__ == "__main__":
    container = punq.Container()
    container.register(ChannelMessageSender, instance=ChannelMessageSender(
        ai_client=GeminiClient(),
        clients_creator=ClientsCreator(TELEGRAM_USERS_TO_COMMENT)
    ))
    channelMessageSender = container.resolve(ChannelMessageSender)
    asyncio.run(channelMessageSender.start_messaging())
