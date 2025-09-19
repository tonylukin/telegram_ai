from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from app.services.ai.ai_client_base import AiClientBase
from app.services.apify.instagram_scrapper_client import InstagramScrapperClient
from app.services.collectors.instagram_user_info_collector import InstagramUserInfoCollector
from app.services.playwright.instagram_playwright_client import InstagramPlaywrightClient
from app.services.proxy.proxy_fetcher_decodo import ProxyFetcherDecodo


@pytest.mark.skip
async def test_get_user_info_playwright_real_user():
    """
    Integration test: fetch real Instagram data for tony.lukin
    Requires: network access and valid Instagram session (if needed).
    """
    collector = InstagramUserInfoCollector(
        instagram_scrapper_client=InstagramPlaywrightClient(proxy_fetcher=ProxyFetcherDecodo()))

    result = await collector._InstagramUserInfoCollector__get_instagram_profile_data("tony.lukin")

    # Basic validations — we don't hardcode follower count as it changes.
    assert isinstance(result, dict)
    assert isinstance(result["followers"], list)
    assert isinstance(result["following"], list)
    assert isinstance(result["posts"], list)
    assert isinstance(result["bio"], str)
    assert len(result["followers"]) >= 0
    assert len(result["following"]) >= 0
    assert len(result["posts"]) >= 0


@pytest.mark.skip
async def test_get_user_info_playwright_not_found(session):
    collector = InstagramUserInfoCollector(session=session, instagram_scrapper_client=InstagramPlaywrightClient(proxy_fetcher=ProxyFetcherDecodo()))
    with pytest.raises(ValueError):
        await collector.get_user_info('nonexistent_user243434324234234324234234')

@pytest.mark.asyncio
async def test_get_user_info_success(ai_client: AiClientBase, session: Session, mock_query: MagicMock):
    mock_session = create_autospec(Session, instance=True)
    mock_session.query.return_value = mock_query
    mock_query.first.return_value = None
    collector = InstagramUserInfoCollector(ai_client=ai_client, session=mock_session, instagram_scrapper_client=InstagramScrapperClient())

    user_info = await collector.get_user_info("tony.lukin")
    assert isinstance(user_info, dict)
    assert user_info['description'] == 'prompt'
