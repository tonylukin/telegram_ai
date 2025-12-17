import asyncio
import punq

from app.dependencies import get_open_ai_client
from app.services.telegram.new_message_channel_message_sender import NewMessageChannelMessageSender
from app.services.telegram.clients_creator import ClientsCreator
from app.db.session import Session as SQLAlchemySession


if __name__ == "__main__":
    container = punq.Container()
    session = SQLAlchemySession()
    container.register(NewMessageChannelMessageSender, instance=NewMessageChannelMessageSender(
        ai_client=get_open_ai_client(),
        clients_creator=ClientsCreator(session)
    ))
    channel_message_sender: NewMessageChannelMessageSender = container.resolve(NewMessageChannelMessageSender)
    asyncio.run(channel_message_sender.send_comments_on_new_messages())
