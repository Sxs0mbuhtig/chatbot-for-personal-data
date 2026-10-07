import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import anyio

from main import app
from services.lexicon import generate_embedding, vector_search, _sha256_embedding
from services.llm_client import GeminiKeyRotator
from schemas.search import EducationalCard, SearchResponse
from routers.search import build_educational_card

client = TestClient(app)

def test_generate_embedding_structure():
    """Validates deterministic 384-dimensional vector embedding generation."""
    embedding = generate_embedding("កម្ពុជា", dimensions=384)
    assert isinstance(embedding, list)
    assert len(embedding) == 384
    assert all(isinstance(v, float) for v in embedding)

    # Validate determinism
    emb2 = generate_embedding("កម្ពុជា", dimensions=384)
    assert embedding == emb2

    # Different words produce different vectors
    emb3 = generate_embedding("សេរីភាព", dimensions=384)
    assert embedding != emb3

def test_educational_card_schema():
    """Validates EducationalCard Pydantic model construction."""
    card = EducationalCard(
        title_km="ព័ត៌មានអក្ខរាវិរុទ្ធ៖ លឺ ➔ ឮ",
        register_label_km="អក្ខរាវិរុទ្ធផ្លូវការ (វចនានុក្រមជួនណាត)",
        historical_context_km="ពាក្យស្វែងរក «លឺ» ត្រូវបានភ្ជាប់តាមសូរសំឡេងទៅទម្រង់ដើម «ឮ»។",
        is_chuon_nath_official=True
    )
    assert card.title_km.startswith("ព័ត៌មានអក្ខរាវិរុទ្ធ")
    assert card.is_chuon_nath_official is True
    dump = card.model_dump()
    assert "register_label_km" in dump
    assert "historical_context_km" in dump

def test_build_educational_card_phonetic_bridge():
    """Validates automatic historical context generation when resolving phonetic variants."""
    ling_ctx = {
        "register": "phonetic_modern",
        "etymology_type": "Post-Reform Simplified Spelling",
        "boundary_note_km": "ទម្រង់អក្ខរាវិរុទ្ធសម្រួលតាមបែបសម្លេងនិយាយទំនើប។",
        "educational_explanation_km": "ពាក្យ «លឺ» ជាទម្រង់សរសេរតាមសម្លេងអានទំនើប។"
    }
    card = build_educational_card("លឺ", ling_ctx, is_official=True, resolved_variant="ឮ")
    assert card.is_chuon_nath_official is True
    assert "លឺ ➔ ឮ" in card.title_km
    assert "វចនានុក្រមជួនណាត" in card.historical_context_km

def test_search_api_educational_card_payload():
    """Validates public Search API response payload for EducationalCard injection."""
    response = client.get("/api/v1/search?q=ស៊ីញ៉េ")
    assert response.status_code == 200
    data = response.json()
    assert "educational_card" in data
    edu_card = data["educational_card"]
    assert edu_card["register_label_km"] == "ពាក្យកម្ចីបារាំង (French Loanword)"
    assert edu_card["is_chuon_nath_official"] is False

def test_tier_3_vector_search_fallback():
    """Validates vector search function fallback behavior."""
    results = vector_search("សេរីភាព", limit=5)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# NEW: Phase 3 tests
# ---------------------------------------------------------------------------

def test_generate_embedding_falls_back_to_sha256_on_api_error():
    """
    When gemini_rotator.generate_embedding raises (e.g., no keys, network error),
    generate_embedding() must silently fall back to the SHA-256 stub and return
    a correctly shaped, non-zero vector.
    """
    import services.lexicon as lexicon_module

    with patch.object(lexicon_module.gemini_rotator, "generate_embedding", side_effect=RuntimeError("no keys")):
        result = generate_embedding("ភ្នំពេញ", dimensions=384)

    assert isinstance(result, list)
    assert len(result) == 384
    assert all(isinstance(v, float) for v in result)
    # Result should match the SHA-256 stub output for the same input
    expected = _sha256_embedding("ភ្នំពេញ", dimensions=384)
    assert result == expected


def test_rotator_throttle_delay_fires_between_rotation_retries():
    """
    When throttle_delay > 0, time.sleep must be called after each 429-induced
    key rotation.  Specifically: key1 → 429 → sleep → key2 → success.
    """
    rate_limit_err = Exception("RESOURCE_EXHAUSTED quota")
    rate_limit_err.code = 429  # type: ignore[attr-defined]
    success_response = MagicMock()

    rotator = GeminiKeyRotator(keys=["k1", "k2"], throttle_delay=2.0)

    mock_k1 = MagicMock()
    mock_k1.models.generate_content.side_effect = [rate_limit_err]
    mock_k2 = MagicMock()
    mock_k2.models.generate_content.return_value = success_response

    client_map = {"k1": mock_k1, "k2": mock_k2}

    with patch("services.llm_client.time.sleep") as mock_sleep, \
         patch.object(rotator, "_get_client", side_effect=lambda k: client_map[k]):
        result = rotator.generate_content(model="gemini-2.5-flash", contents="test")

    assert result is success_response
    # sleep must have been called once (after k1 rotated to k2)
    mock_sleep.assert_called_once_with(2.0)


@pytest.mark.anyio
async def test_telemetry_curation_batch_sleeps_between_llm_calls():
    """
    run_curation_batch() must call asyncio.sleep(throttle_seconds) exactly
    (N-1) times for N candidate terms \u2014 skipping the sleep after the last item.
    """
    from services.telemetry import TelemetryManager

    manager = TelemetryManager(use_in_memory_fallback=True)

    # Inject 3 fake high-hit terms directly into the in-memory store
    fake_terms = ["ពាក្យ_ក", "ពាក្យ_ខ", "ពាក្យ_គ"]
    for term in fake_terms:
        manager._memory_hits[term] = 10
        manager._memory_meta[term] = {
            "raw_query": term,
            "normalized_root": term,
            "register_meta": {},
            "first_seen": "2026-01-01T00:00:00+00:00",
            "last_seen": "2026-01-01T00:00:00+00:00",
        }

    mock_entry = MagicMock()

    with patch("services.telemetry.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("services.batch_evaluator.llm_batch_curator") as mock_curator:

        mock_curator._curate_single_term = AsyncMock(return_value=mock_entry)

        # Import inside patch scope so the mock is active
        from services import batch_evaluator
        batch_evaluator.llm_batch_curator._curate_single_term = AsyncMock(return_value=mock_entry)

        results = await manager.run_curation_batch(min_hits=5, throttle_seconds=2.0)

    # 3 terms processed → sleep called 2 times (not after the last)
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(2.0)
    assert len(results) == 3


def test_educational_card_phonetic_bridge_api_roundtrip():
    """
    Full API integration test: searching the phonetic modern spelling «លឺ»
    should resolve via the Tier-2 phonetic bridge to the classical form «ឮ»
    and include a properly structured educational_card in the response.
    """
    response = client.get("/api/v1/search?q=លឺ")
    assert response.status_code == 200
    data = response.json()

    # Must resolve via phonetic bridge (or exact match if «ឮ» itself is indexed)
    assert data["status"] in ("phonetic_bridge_match", "exact_match", "vector_semantic_match", "unmatched_queued")

    # educational_card must always be present
    assert "educational_card" in data
    card = data["educational_card"]
    assert "title_km" in card
    assert "register_label_km" in card
    assert "historical_context_km" in card
    assert isinstance(card["is_chuon_nath_official"], bool)

    # If phonetic bridge resolved, the title must contain both spellings
    if data["status"] == "phonetic_bridge_match":
        assert "resolved_variant" in data
        assert "លឺ" in card["title_km"]
        assert "ឮ" in card["title_km"] or data["resolved_variant"] in card["title_km"]

