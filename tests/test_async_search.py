import asyncio
import pytest
import httpx
from main import app

from unittest.mock import patch

@pytest.mark.asyncio
@patch("routers.search.typesense_client")
async def test_search_resolution_loanwords_async(mock_typesense):
    # Mock Typesense search response
    mock_typesense.collections["dictionary"].documents.search.return_value = {
        "hits": [{"document": {"headword": "ស៊ីញ៉េ", "definition": "French loanword for signature"}}]
    }
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/search", params={"q": "ស៊ីញ៉េ"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "ស៊ីញ៉េ"
    assert data["status"] in ["loanword_match", "exact_match", "phonetic_bridge_match"]

@pytest.mark.asyncio
async def test_concurrent_search_load():
    """Validates concurrent load handling for Phase 1.3 concurrency requirements."""
    terms = ["ស៊ីញ៉េ", "ប្រេកង់", "បាក់តេរី", "រ៉ាដា"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), 
        base_url="http://test"
    ) as ac:
        tasks = [ac.get("/api/v1/search", params={"q": term}) for term in terms]
        responses = await asyncio.gather(*tasks)
        
        for resp in responses:
            assert resp.status_code == 200
            assert "query" in resp.json()
