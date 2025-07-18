import asyncio
import punq
import argparse

from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.reaction_sender import ReactionSender
from app.services.telegram.clients_creator import ClientsCreator
from app.models.bot import Bot


if __name__ == "__main__":
    container = punq.Container()
    container.register(ReactionSender, instance=ReactionSender(
        clients_creator=ClientsCreator([Bot.ROLE_REACT]),
        chat_searcher=ChatSearcher(),
    ))
    reaction_sender = container.resolve(ReactionSender)

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="Query to find groups for reactions", required=True)
    args = parser.parse_args()
    asyncio.run(reaction_sender.send_reactions(query=args.query))
