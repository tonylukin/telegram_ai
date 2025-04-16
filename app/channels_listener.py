import asyncio
import punq

from app.services.ai.gemini_client import GeminiClient
from app.services.telegram.channel_message_sender import ChannelMessageSender

if __name__ == "__main__":
    container = punq.Container()
    container.register(ChannelMessageSender, instance=ChannelMessageSender(
        ai_client=GeminiClient()
    ))
    channelMessageSender = container.resolve(ChannelMessageSender)
    asyncio.run(channelMessageSender.start_messaging())
