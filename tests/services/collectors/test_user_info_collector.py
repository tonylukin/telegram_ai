from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from app.db.queries.bot import get_bots
from app.services.ai.ai_client_base import AiClientBase
from app.services.collectors.user_info_collector import UserInfoCollector
from app.services.telegram.chat_searcher import ChatSearcher
from app.services.telegram.clients_creator import ClientsCreator
from app.services.telegram.user_instance_searcher import UserInstanceSearcher
from app.services.telegram.user_messages_search import UserMessagesSearch


@pytest.mark.asyncio
async def test_user_info_collector(ai_client: AiClientBase, session: Session, mock_query: MagicMock):
    bots = get_bots(session=session)
    mock_session = create_autospec(Session, instance=True)
    mock_session.query.return_value = mock_query
    mock_query.first.return_value = None
    chat_searcher = ChatSearcher()

    clients_creator = ClientsCreator(session=mock_session)

    collector = UserInfoCollector(
        clients_creator=clients_creator,
        session=mock_session,
        ai_client=ai_client,
        chat_searcher=chat_searcher,
        user_messages_search=UserMessagesSearch(),
        user_instance_searcher=UserInstanceSearcher(clients_creator=clients_creator, chat_searcher=chat_searcher),
    )

    for bot in bots:
        mock_query.all.return_value = [bot]
        user_info = await collector.get_user_info(username="@tonylukin", channel_usernames=['@irvinefriends'])
        assert isinstance(user_info, dict)
        assert user_info['description'] == 'prompt'
