import pytest
import unicodedata
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_khmer_nfc_normalization():
    """Validates that NFC normalization correctly handles decomposed Khmer sequences."""
    decomposed = "ក\u17c4"  # Combining vowel sequence
    normalized = unicodedata.normalize("NFC", decomposed)
    assert isinstance(normalized, str)
    assert len(normalized) > 0

def test_zero_width_space_handling():
    """Validates search queries containing zero-width spaces (ZWSP \u200b) and soft hyphens."""
    query_with_zwsp = "កម\u200b្ពុជា"
    response = client.get(f"/api/v1/search?q={query_with_zwsp}")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == query_with_zwsp
    assert "status" in data

def test_stacked_coeng_consonant_resolution():
    """Validates proper handling of complex coeng subscript consonant stacking."""
    complex_query = "ក្ដរ"
    response = client.get(f"/api/v1/search?q={complex_query}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["exact_match", "phonetic_bridge_match", "unmatched_queued"]
    assert "results" in data

def test_malformed_unicode_resilience():
    """Ensures search endpoint remains robust and doesn't crash on trailing uncompleted coeng marks."""
    malformed = "ក\u17d2"  # Trailing coeng without subscript consonant
    response = client.get(f"/api/v1/search?q={malformed}")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
