import pytest

from app.services.collectors.instagram_user_info_collector import InstagramUserInfoCollector
from app.services.playwright.instagram_playwright_client import InstagramPlaywrightClient
from app.services.proxy.proxy_fetcher_decodo import ProxyFetcherDecodo


@pytest.mark.asyncio
async def test_get_user_info_real_user():
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


@pytest.mark.asyncio
async def test_get_user_info_not_found(session):
    collector = InstagramUserInfoCollector(session=session, instagram_scrapper_client=InstagramPlaywrightClient(proxy_fetcher=ProxyFetcherDecodo()))
    with pytest.raises(ValueError):
        await collector.get_user_info('nonexistent_user243434324234234324234234')

# @pytest.mark.asyncio
# async def test_get_user_info_success(collector, mock_fetch_user_info):
#     mock_fetch_user_info.return_value = {
#         "username": "test_user",
#         "followers": 123,
#         "bio": "Test bio"
#     }
#
#     result = await collector.get_user_info("test_user")
#
#     assert result["username"] == "test_user"
#     assert result["followers"] == 123
#     assert result["bio"] == "Test bio"
#     mock_fetch_user_info.assert_awaited_once_with("test_user")
