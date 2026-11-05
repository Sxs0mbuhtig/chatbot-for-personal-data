import asyncio
import pytest
import httpx
from main import app
import os
from dotenv import load_dotenv

# Automatically load .env variables before any test fixtures or app modules load
load_dotenv(override=True)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def async_client():
    """Session-scoped async HTTP client for FastAPI tests."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
