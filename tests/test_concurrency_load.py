import pytest
import asyncio
import httpx
from main import app

@pytest.mark.asyncio
async def test_high_concurrency_search_load():
    """Simulates high-concurrency search request bursts (60+ simultaneous requests) against FastAPI endpoint."""
    queries = [
        "កម្ពុជា", "កង", "សេចក្តី", "វចនានុក្រម", "អក្សរ", 
        "បារាំង", "ហ្វ្លូ", "ស៊ីញ៉េ", "តេងតាងៗ", "ពាក្យមិនស្គាល់៩៩"
    ]
    
    # Use ASGITransport for high-performance in-memory async testing with httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        tasks = []
        for i in range(60):
            q = queries[i % len(queries)]
            tasks.append(ac.get(f"/api/v1/search?q={q}"))
        
        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)
        
        # Validate response integrity across all concurrent workers
        for resp in responses:
            assert resp.status_code == 200
            data = resp.json()
            assert "query" in data
            assert "status" in data
            assert "results" in data
