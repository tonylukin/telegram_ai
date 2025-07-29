import asyncio
import punq
import argparse

from app.dependencies import get_db
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.reaction_sender import ReactionSender
from app.services.telegram.clients_creator import ClientsCreator


if __name__ == "__main__":
    container = punq.Container()
    container.register(ReactionSender, instance=ReactionSender(
        clients_creator=ClientsCreator(get_db()),
        chat_searcher=ChatSearcher(),
    ))
    reaction_sender: ReactionSender = container.resolve(ReactionSender)

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="Query to find groups for reactions", required=True)
    args = parser.parse_args()
    asyncio.run(reaction_sender.send_reactions(query=args.query))
