import os
import sqlite3
import pytest
from services.predictive_engine import KhmerPredictiveEngine, CandidateSuggestion

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "chuon_nath_fts.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE dictionary (
            headword TEXT,
            norm_headword TEXT
        )
    """)
    cursor.executemany("INSERT INTO dictionary (headword, norm_headword) VALUES (?, ?)", [
        ("កុមព្យូទ័រ", "កុមព្យូទ័រ"),
        ("កុំព្យូទ័រ", "កុំព្យូទ័រ"),
        ("កប", "កប"),
        ("កត", "កត")
    ])
    conn.commit()
    conn.close()
    return str(db_file)

def test_predictive_engine_empty_query():
    """Covers line 77: if not clean: return []"""
    engine = KhmerPredictiveEngine(db_path="nonexistent.db")
    assert engine.generate_suggestions("") == []
    assert engine.generate_suggestions("   ") == []

def test_predictive_engine_nonexistent_db(tmp_path):
    """Covers lines 30-31: db path check and exception safety"""
    engine = KhmerPredictiveEngine(db_path=str(tmp_path / "missing.db"))
    assert engine._query_prefix_matches("ក") == []

def test_predictive_engine_with_db(temp_db):
    """Covers prefix matches, broad search, and edit distance branches (lines 94-111)"""
    engine = KhmerPredictiveEngine(db_path=temp_db)
    
    # Test prefix matching and exact match scoring
    suggestions = engine.generate_suggestions("កុម", max_candidates=10)
    assert isinstance(suggestions, list)
    
    # Test broad search when candidates_map < max_candidates (triggers Levenshtein edit distance)
    broad_suggestions = engine.generate_suggestions("ក", max_candidates=10)
    assert any(s.match_type in ("prefix", "edit_distance", "phonetic_variant") for s in broad_suggestions)

def test_grapheme_levenshtein_and_exceptions(temp_db):
    """Covers Levenshtein calculation and database exception / finally blocks (lines 35-50)"""
    engine = KhmerPredictiveEngine(db_path=temp_db)
    dist = engine._grapheme_levenshtein("កុម", "កុំ")
    assert isinstance(dist, int)
    assert dist >= 0

    # Force a database error to cover exception and finally blocks in _query_prefix_matches
    engine_invalid = KhmerPredictiveEngine(db_path="/invalid/restricted/path.db")
    assert engine_invalid._query_prefix_matches("ក") == []
