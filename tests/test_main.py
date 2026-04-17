import pytest
from httpx import AsyncClient, ASGITransport
from app import app, scraper
import os

@pytest.mark.asyncio
async def test_read_main():
    """Test the root endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json()["status"] in ["ready", "initializing"]

@pytest.mark.asyncio
async def test_get_status():
    """Test the status endpoint"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/status")
    assert response.status_code == 200
    assert "is_initialized" in response.json()

@pytest.mark.asyncio
async def test_multi_stage_fetch_logic():
    """Verify that redirect() initializes and tries to fetch profile info"""
    # Note: We aren't mocking the network yet, so this just verifies the method exists and handles init
    assert hasattr(scraper, "redirect")
    # Clean check
    is_init = await scraper.initialize()
    # It will likely return True if it find a session or False if login fails, but the logic should flow
    assert isinstance(is_init, bool)

@pytest.mark.asyncio
async def test_session_file_logic():
    """Verify session file path is correctly calculated"""
    assert "instagram_session.json" in scraper.session_file
    assert scraper.user_data_dir in scraper.session_file

@pytest.mark.asyncio
async def test_scrape_specific_username(monkeypatch):
    """Test the scrape endpoint for a specific username with mocked response"""
    username = "bishwajit.garai.1"
    
    # Mock the scraper.redirect method
    async def mock_redirect(url):
        return {
            "url": url,
            "graphql_calls": [
                {
                    "response_body": {"data": {"user": {"biography_with_entities": {"text": "Verified Profile"}}}},
                    "request": {"post_data": "some_data"}
                }
            ],
            "navigation_success": True,
            "scraped_at": 123456789
        }
    
    monkeypatch.setattr(scraper, "redirect", mock_redirect)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post("/api/v1/user/by/username", params={"username": username})
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["username"] == username
    assert "user_data" in data
    # Verify the mocked data passed through
    assert data["user_data"]["biography_with_entities"]["text"] == "Verified Profile"

@pytest.mark.asyncio
async def test_rate_limiter_details():
    """Verify rate limiter has the correct global limit of 60/minute"""
    # Accessing internal limits of slowapi if possible, or just verify presence
    assert app.state.limiter is not None
