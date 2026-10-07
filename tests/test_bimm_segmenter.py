import pytest
from services.composite_etymology_engine import composite_etymology_engine, KhmerCompositeEtymologyEngine

def test_bimm_segmenter_basic():
    """Validates BiMM word segmentation on continuous unspaced Khmer input strings."""
    engine = KhmerCompositeEtymologyEngine()
    # Test segmentation on single word vs compound terms
    tokens = engine.segment_bimm("កម្ពុជា")
    assert isinstance(tokens, list)
    assert len(tokens) >= 1
    assert "".join(tokens) == "កម្ពុជា"

def test_bimm_segmenter_grapheme_integrity():
    """Validates that BiMM segmenter preserves all Khmer visual graphemes without dropping characters."""
    engine = KhmerCompositeEtymologyEngine()
    phrase = "សន្តិភាពនិងអភិវឌ្ឍន៍"
    tokens = engine.segment_bimm(phrase)
    reconstructed = "".join(tokens)
    assert reconstructed == phrase

def test_bimm_integration_in_composite_etymology_engine():
    """Validates that composite etymology engine uses BiMM segmenter for unspaced input."""
    res = composite_etymology_engine.analyze_term("កម្ពុជា")
    assert hasattr(res, "components")
    assert len(res.components) >= 1
    comp_texts = [c.component for c in res.components]
    assert "".join(comp_texts) == "កម្ពុជា"
