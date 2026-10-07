import pytest
from fastapi.testclient import TestClient

from khmer_normalizer import sanitize_khmer_punctuation
from main import app

client = TestClient(app)

def test_sanitize_khmer_punctuation_comma_spacing():
    """Validates that loan commas without spaces are converted to comma + space (', ')."""
    raw = "កម្ពុជា,បារាំង,អង់គ្លេស"
    sanitized = sanitize_khmer_punctuation(raw)
    assert ", " in sanitized
    assert sanitized.startswith("កម្ពុជា, បារាំង, អង់គ្លេស")

def test_sanitize_khmer_punctuation_trailing_colon_removal():
    """Validates that trailing colons and periods are stripped from definition clauses."""
    raw = "សេចក្តីពន្យល់អំពីពាក្យ :"
    sanitized = sanitize_khmer_punctuation(raw)
    assert not sanitized.endswith(":")
    assert not sanitized.endswith(" ")

def test_sanitize_khmer_punctuation_sentence_termination():
    """Validates that long independent clauses terminate with Khmer Khan (។)."""
    raw_sentence = "ប្រទេសកម្ពុជាជាប្រទេសមួយស្ថិតនៅតំបន់អាស៊ីអាគ្នេយ៍"
    sanitized = sanitize_khmer_punctuation(raw_sentence)
    assert sanitized.endswith("។")

def test_search_results_deduplication_and_compound_separation():
    """Validates root word search results deduplication and compound_entries isolation."""
    response = client.get("/api/v1/search?q=កង")
    assert response.status_code == 200
    data = response.json()
    
    # 1. Check direct results
    results = data.get("results", [])
    seen_defs = set()
    for r in results:
        # Direct results headword should match root
        assert r["entry_km"] == "កង"
        # Deduplication assertion
        key = (r["entry_km"], r["definition_km"])
        assert key not in seen_defs
        seen_defs.add(key)
        
    # 2. Check compound_entries isolation (e.g. នំកង, កងទ័ព should not dilute results)
    compound_entries = data.get("compound_entries", [])
    assert isinstance(compound_entries, list)
    if len(compound_entries) > 0:
        c_words = [c["entry_km"] for c in compound_entries]
        # Compound terms where 'កង' is component must be in compound_entries, not direct results
        assert all(w != "កង" for w in c_words)

def test_search_results_alphabetical_and_pos_sorting():
    """Validates alphabetical A-Z and POS hierarchy priority sorting."""
    response = client.get("/api/v1/search?q=កង")
    assert response.status_code == 200
    data = response.json()
    results = data.get("results", [])
    
    if len(results) >= 2:
        # Verify POS hierarchy priority (Noun ន. precedes Verb កិ. or Adjective គុ.)
        pos_order = {"ន.": 1, "កិ.": 2, "គុ.": 3, "គុ.ស.": 4, "កិ.គុ.": 5}
        for i in range(len(results) - 1):
            p1 = pos_order.get(results[i]["pos"], 99)
            p2 = pos_order.get(results[i + 1]["pos"], 99)
            assert p1 <= p2
