import pytest
from unittest.mock import AsyncMock, patch
from app.services.collectors.instagram_user_info_collector import InstagramUserInfoCollector
from app.db.session import Session


@pytest.fixture
def collector():
    """Returns a fresh InstagramUserInfoCollector instance for each test."""
    return InstagramUserInfoCollector()

@pytest.fixture
def session():
    db = Session()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def mock_fetch_user_info():
    """
    Automatically patches the private __fetch_user_info method.
    You can override its return_value or side_effect inside tests.
    """
    with patch.object(
        InstagramUserInfoCollector,
        "_InstagramUserInfoCollector__get_instagram_profile_data",
        new_callable=AsyncMock
    ) as mock:
        yield mock
