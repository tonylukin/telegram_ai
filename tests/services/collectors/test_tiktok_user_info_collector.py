from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from app.services.ai.ai_client_base import AiClientBase
from app.services.apify.tiktok_scrapper_client import TikTokScrapperClient
from app.services.collectors.tiktok_user_info_collector import TikTokUserInfoCollector


@pytest.mark.asyncio
async def test_get_user_info_success(ai_client: AiClientBase, session: Session, mock_query: MagicMock):
    mock_session = create_autospec(Session, instance=True)
    mock_session.query.return_value = mock_query
    mock_query.first.return_value = None
    collector = TikTokUserInfoCollector(ai_client=ai_client, session=mock_session, tiktok_scrapper_client=TikTokScrapperClient())

    user_info = await collector.get_user_info("kallmekris")
    assert isinstance(user_info, dict)
    assert user_info['description'] == 'prompt'
