import asyncio
import punq
import argparse

from app.dependencies import get_db, get_ai_client
from app.services.telegram.message_receiver import MessageReceiver
from app.services.telegram.clients_creator import ClientsCreator
from app.db.session import Session as SQLAlchemySession


if __name__ == "__main__":
    container = punq.Container()
    session = SQLAlchemySession()
    container.register(MessageReceiver, instance=MessageReceiver(
        ai_client=get_ai_client(),
        clients_creator=ClientsCreator(session)
    ))
    message_receiver: MessageReceiver = container.resolve(MessageReceiver)

    parser = argparse.ArgumentParser()
    parser.add_argument("--bot", help="Bot name to listen messages", required=True)
    args = parser.parse_args()

    asyncio.run(message_receiver.get_new_messages_for_bot(bot_name=args.bot))
