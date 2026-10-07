import pytest
from fastapi.testclient import TestClient

from main import app
from khmer_normalizer import (
    clean_khmer_text,
    count_khmer_graphemes,
    extract_echo_roots,
    get_independent_vowel_variants
)
from services.expressive_engine import KhmerExpressiveEngine
from services.batch_evaluator import BatchTelemetryEvaluator

client = TestClient(app)

def test_grapheme_counting_with_lek_to():
    """Validates that U+17D7 (ៗ / Lek To) is counted as an independent visual grapheme token."""
    text = "តេងតាងៗ"
    count = count_khmer_graphemes(text)
    # តេ + ង + តា + ង + ៗ = 5 grapheme tokens
    assert count == 5
    
    simple_lek_to = "ង៉ុកៗ"
    assert count_khmer_graphemes(simple_lek_to) == 3

def test_extract_echo_roots():
    """Validates echo compound decomposition into constituent root syllables."""
    roots = extract_echo_roots("ងីងើ")
    assert roots == ["ងី", "ងើ", "ងីងើ"]

    roots_lek_to = extract_echo_roots("តេងតាងៗ")
    assert roots_lek_to == ["តេង", "តាង", "តេងតាង"]

def test_independent_vowel_bridging():
    """Validates classical <-> modern phonetic independent vowel variant generation."""
    vars_lue = get_independent_vowel_variants("លឺ")
    assert "ឮ" in vars_lue

    vars_roleuk = get_independent_vowel_variants("រលឹក")
    assert "រឭក" in vars_roleuk

    vars_reus = get_independent_vowel_variants("ឫស")
    assert "រឹស" in vars_reus

def test_register_and_etymology_detection():
    """Validates register and etymology classification across different Khmer registers."""
    engine = KhmerExpressiveEngine()

    # Expressive / Onomatopoeia
    res_expressive = engine.digest_input("ឡេឡឺ")
    assert res_expressive.register_analysis.primary_register == "expressive_onomatopoeia"
    assert res_expressive.linguistic_context.etymology_type == "Expressive Onomatopoeia"

    res_lek_to = engine.digest_input("តេងតាងៗ")
    assert res_lek_to.register_analysis.primary_register == "expressive_onomatopoeia"

    res_ngok = engine.digest_input("ង៉ុកៗ")
    assert res_ngok.register_analysis.primary_register == "expressive_onomatopoeia"

    # Franco-Khmer Loanwords
    res_signe = engine.digest_input("ស៊ីញ៉េ")
    assert res_signe.register_analysis.primary_register == "franco_khmer_loanword"
    assert res_signe.linguistic_context.etymology_type == "French Loanword"

    res_code = engine.digest_input("កូដ")
    assert res_code.register_analysis.primary_register == "franco_khmer_loanword"

    # Km-English Rap Fusion
    res_flow = engine.digest_input("ហ្វ្លូ")
    assert res_flow.register_analysis.primary_register == "km_english_fusion"
    assert res_flow.linguistic_context.etymology_type == "English Loanword"

    res_bro = engine.digest_input("ប្រូ")
    assert res_bro.register_analysis.primary_register == "km_english_fusion"

    # Formal Classical vs Phonetic Modern
    res_classical = engine.digest_input("រឭក")
    assert res_classical.register_analysis.primary_register == "formal_classical"

    res_modern = engine.digest_input("រលឹក")
    assert res_modern.register_analysis.primary_register == "phonetic_modern"

def test_search_resolution_loanwords_and_expressives():
    """Validates API search resolution endpoint for expressives, loanwords, and phonetic pairs."""
    # Loanword resolution: ស៊ីញ៉េ
    response = client.get("/api/v1/search?q=ស៊ីញ៉េ")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "ស៊ីញ៉េ"
    assert data["status"] in ["loanword_match", "exact_match", "phonetic_bridge_match"]
    assert "linguistic_context" in data
    assert data["linguistic_context"]["register"] == "franco_khmer_loanword"

    # Urban Rap loanword resolution: ហ្វ្លូ
    response = client.get("/api/v1/search?q=ហ្វ្លូ")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "ហ្វ្លូ"
    assert "linguistic_context" in data
    assert data["linguistic_context"]["register"] == "km_english_fusion"

    # Reduplicated expressive resolution: តេងតាងៗ
    response = client.get("/api/v1/search?q=តេងតាងៗ")
    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "តេងតាងៗ"
    assert "linguistic_context" in data
    assert data["linguistic_context"]["register"] == "expressive_onomatopoeia"

def test_batch_telemetry_evaluator(tmp_path):
    """Validates batch telemetry evaluator queueing and candidate aggregation."""
    evaluator = BatchTelemetryEvaluator(storage_dir=str(tmp_path))
    
    evaluator.queue_unmatched_query("ឡឺកីកី", "ឡឺកីកី", "expressive_onomatopoeia", "127.0.0.1")
    evaluator.queue_unmatched_query("ឡឺកីកី", "ឡឺកីកី", "expressive_onomatopoeia", "127.0.0.1")

    report = evaluator.evaluate_batch(min_hits=1)
    assert report.total_unmatched_unique == 1
    assert len(report.high_priority_candidates) == 1
    assert report.high_priority_candidates[0].query == "ឡឺកីកី"
    assert report.high_priority_candidates[0].count == 2
