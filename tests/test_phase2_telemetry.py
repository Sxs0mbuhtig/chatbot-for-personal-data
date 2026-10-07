import pytest
import asyncio
import fakeredis.aioredis
from fastapi.testclient import TestClient

from main import app
from services.telemetry import TelemetryManager, telemetry_manager
from services.batch_evaluator import LLMBatchCurator, KhmerLinguisticEntry
from routers.admin import router as admin_router

client = TestClient(app)

@pytest.fixture
def fake_telemetry_manager():
    """Fixture providing an isolated TelemetryManager backed by FakeRedis."""
    tm = TelemetryManager(use_in_memory_fallback=True)
    fake_client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    tm._redis_client = fake_client
    return tm

@pytest.mark.asyncio
async def test_redis_telemetry_record_and_fetch(fake_telemetry_manager):
    """Validates Redis sorted set counter incrementing and metadata storage."""
    tm = fake_telemetry_manager
    
    await tm.record_unresolved_query("ពាក្យប្លែក១", "ពាក្យប្លែក១", {"primary_register": "colloquial_general"})
    await tm.record_unresolved_query("ពាក្យប្លែក១", "ពាក្យប្លែក១", {"primary_register": "colloquial_general"})
    await tm.record_unresolved_query("ពាក្យប្លែក២", "ពាក្យប្លែក២", {"primary_register": "expressive_onomatopoeia"})

    top = await tm.get_top_unresolved_queries(limit=10)
    assert len(top) == 2
    assert top[0]["term"] == "ពាក្យប្លែក១"
    assert top[0]["hits"] == 2
    assert top[1]["term"] == "ពាក្យប្លែក២"
    assert top[1]["hits"] == 1

    # Clear evaluated terms
    await tm.clear_processed_queries(["ពាក្យប្លែក១"])
    top_after = await tm.get_top_unresolved_queries(limit=10)
    assert len(top_after) == 1
    assert top_after[0]["term"] == "ពាក្យប្លែក២"

@pytest.mark.asyncio
async def test_llm_batch_curator_validation():
    """Validates LLM Batch Curator output schema and Pydantic validation."""
    curator = LLMBatchCurator()
    
    # Record a test unresolved query into telemetry_manager
    await telemetry_manager.record_unresolved_query("ហ្វ្លូ-ស្លែង", "ហ្វ្លូ-ស្លែង", {"primary_register": "km_english_fusion"})
    await telemetry_manager.record_unresolved_query("ហ្វ្លូ-ស្លែង", "ហ្វ្លូ-ស្លែង", {"primary_register": "km_english_fusion"})

    # Evaluate batch with min_hits=2
    entries = await curator.evaluate_batch(min_hits=2)
    assert isinstance(entries, list)
    assert len(entries) >= 1
    
    entry = entries[0]
    assert isinstance(entry, KhmerLinguisticEntry)
    assert entry.input_term == "ហ្វ្លូ-ស្លែង"
    assert entry.norm_root == "ហ្វ្លូ-ស្លែង"
    assert entry.historical_context.boundary_note_km != ""
    assert entry.historical_context.educational_explanation_km != ""
    assert 0.0 <= entry.confidence_score <= 1.0

def test_search_background_telemetry_integration():
    """Validates that search endpoint dispatches async background telemetry without HTTP failure."""
    query = "ពាក្យមិនស្គាល់៩៩"
    response = client.get(f"/api/v1/search?q={query}")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == query
    assert data["status"] == "unmatched_queued"
    assert data["total"] == 0
    assert "linguistic_context" in data

def test_admin_telemetry_top_endpoint():
    """Validates GET /api/v1/admin/telemetry/top route."""
    response = client.get("/api/v1/admin/telemetry/top?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_admin_curate_telemetry_endpoint():
    """Validates POST /api/v1/admin/curate-telemetry pipeline endpoint."""
    response = client.post("/api/v1/admin/curate-telemetry?min_hits=1&auto_index=false")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "processed_count" in data
    assert "curated_entries" in data
    assert isinstance(data["curated_entries"], list)
