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
async def test_scraper_initialization_state():
    """
    Test that the scraper class has the correct attributes 
    without actually launching a browser (which would fail in CI).
    """
    assert hasattr(scraper, "user_data_dir")
    assert hasattr(scraper, "initialize")
    assert hasattr(scraper, "redirect")
    
    # Since we are using the httpx scraper now, let's check for httpx client
    assert hasattr(scraper, "client")

@pytest.mark.asyncio
async def test_rate_limiter_exists():
    """Test that the rate limiter is correctly integrated"""
    assert hasattr(app.state, "limiter")
