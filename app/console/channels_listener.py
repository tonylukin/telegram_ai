import asyncio
import punq

from app.dependencies import get_db
from app.services.ai.gemini_client import GeminiClient
from app.services.telegram.new_message_channel_message_sender import NewMessageChannelMessageSender
from app.services.telegram.clients_creator import ClientsCreator


if __name__ == "__main__":
    container = punq.Container()
    container.register(NewMessageChannelMessageSender, instance=NewMessageChannelMessageSender(
        ai_client=GeminiClient(),
        clients_creator=ClientsCreator(get_db())
    ))
    channelMessageSender: NewMessageChannelMessageSender = container.resolve(NewMessageChannelMessageSender)
    asyncio.run(channelMessageSender.send_comments_on_new_messages())
