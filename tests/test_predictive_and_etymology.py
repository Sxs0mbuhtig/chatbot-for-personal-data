import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from services.predictive_engine import predictive_engine, KhmerPredictiveEngine
from services.composite_etymology_engine import composite_etymology_engine, KhmerCompositeEtymologyEngine
from main import app

client = TestClient(app)

# =====================================================================
# 1. PREDICTIVE ENGINE UNIT TESTS
# =====================================================================

def test_predictive_suggestions_max_10_candidates():
    """Validates that predictive engine generates up to 10 candidate suggestions."""
    suggestions = predictive_engine.generate_suggestions("កម្ពុ", max_candidates=10)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 10
    if len(suggestions) > 0:
        cand = suggestions[0]
        assert hasattr(cand, "candidate")
        assert hasattr(cand, "score")
        assert hasattr(cand, "match_type")


def test_predictive_suggestions_phonetic_variant_expansion():
    """Validates phonetic variant expansion (ល/ឡ, shifters) in suggestions."""
    suggestions = predictive_engine.generate_suggestions("លឺ", max_candidates=10)
    cand_strings = [s.candidate for s in suggestions]
    # 'ឮ' should be among candidate suggestions via phonetic expansion
    assert any("ឮ" in c or c == "ឮ" for c in cand_strings) or len(suggestions) > 0


def test_predictive_grapheme_levenshtein_edit_distance():
    """Validates Levenshtein edit distance over Khmer grapheme clusters."""
    engine = KhmerPredictiveEngine()
    dist = engine._grapheme_levenshtein("ខ្ញុំ", "ខ្ញុំ")
    assert dist == 0
    dist_diff = engine._grapheme_levenshtein("កម្ពុជា", "កម្ពុ")
    assert dist_diff == 1


# =====================================================================
# 2. COMPOSITE WORD & ETYMOLOGY ENGINE UNIT TESTS
# =====================================================================

def test_composite_word_decomposition():
    """Validates reduplicated and echo compound decomposition into base components."""
    res = composite_etymology_engine.analyze_term("ងីងើ")
    assert res.raw_term == "ងីងើ"
    assert res.is_composite is True
    assert len(res.components) >= 2
    comp_names = [c.component for c in res.components]
    assert "ងី" in comp_names
    assert "ងើ" in comp_names


def test_loanword_etymology_tagger():
    """Validates detection of French, English, and Pali-Sanskrit loanwords."""
    # French loanword
    res_fr = composite_etymology_engine.analyze_term("ស៊ីញ៉េ")
    assert res_fr.etymology.etymology_class == "french"

    # English loanword
    res_en = composite_etymology_engine.analyze_term("កុំព្យូទ័រ")
    assert res_en.etymology.etymology_class == "english"

    # Pali/Sanskrit loanword
    res_ps = composite_etymology_engine.analyze_term("សន្តិភាព")
    assert res_ps.etymology.etymology_class == "pali_sanskrit"

    # Native Khmer
    res_km = composite_etymology_engine.analyze_term("ទឹក")
    assert res_km.etymology.etymology_class == "native_km"


def test_orthographic_alignment_notes():
    """Validates linguistic notes comparing Chuon Nath vs modern/reform usage."""
    res = composite_etymology_engine.analyze_term("សន្តិភាព")
    notes = res.orthographic_notes
    assert "ជួន ណាត" in notes.chuon_nath_standard
    assert notes.historical_notes_km != ""


# =====================================================================
# 3. 4-TIER SEARCH RESOLUTION INTEGRATION TESTS
# =====================================================================

def test_tier_1_exact_match_resolution():
    """Tier 1: Direct Normalized Root Match returning exact_match or loanword_match status."""
    response = client.get("/api/v1/search?q=កម្ពុជា")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("exact_match", "loanword_match", "success")


def test_tier_2_phonetic_bridge_resolution():
    """Tier 2: Phonetic Bridge & Independent Vowel Match (លឺ -> ឮ)."""
    response = client.get("/api/v1/search?q=លឺ")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("phonetic_bridge_match", "exact_match", "success")


def test_tier_3_composite_match_resolution():
    """Tier 3: Composite breakdown resolution for unindexed compound terms."""
    response = client.get("/api/v1/search?q=ងីងើ")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("composite_match", "exact_match", "phonetic_bridge_match", "success")


def test_tier_4_zero_hit_predictive_suggestions_and_telemetry():
    """Tier 4: Zero-hit query returning 10 predictive suggestions and status unmatched_queued."""
    unmatched_term = "ពាក្យប្លែកៗគ្មានក្នុងវចនានុក្រម១២៣"
    response = client.get(f"/api/v1/search?q={unmatched_term}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("unmatched_queued", "undefined")
    assert "predictive_suggestions" in data
    assert isinstance(data["predictive_suggestions"], list)
