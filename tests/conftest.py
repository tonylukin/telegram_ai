import pytest
from unittest.mock import AsyncMock, patch, create_autospec, MagicMock

from app.services.ai.ai_client_base import AiClientBase
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
def ai_client():
    mock_ai_client = create_autospec(AiClientBase, instance=True)
    # configure the methods
    mock_ai_client.generate_text.return_value = "prompt"
    mock_ai_client.generate_image.return_value = "image.png"
    return mock_ai_client

@pytest.fixture
def mock_query():
    _mock_query = MagicMock()
    _mock_query.filter.return_value = _mock_query
    _mock_query.filter_by.return_value = _mock_query
    _mock_query.order_by.return_value = _mock_query
    _mock_query.limit.return_value = _mock_query
    return _mock_query

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
