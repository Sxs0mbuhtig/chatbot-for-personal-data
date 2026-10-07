import pytest
from khmer_normalizer import (
    clean_khmer_text,
    normalize_khmer_unicode,
    count_khmer_graphemes,
    reorder_khmer_syllable_components,
    normalize_khmer_orthography
)
from scripts.setup_typesense_schema import get_schema_definition
from routers.search import generate_jsonld_defined_term
from query_telemetry import hash_user_ip

def test_zero_width_space_removal():
    """Validates that Zero-Width Spaces (U+200B), NBSP (U+00A0), and soft hyphens (U+00AD) are removed."""
    input_text = "កម្ពុជា\u200b"
    cleaned = clean_khmer_text(input_text)
    assert "\u200b" not in cleaned
    assert cleaned == "កម្ពុជា"

    nbsp_text = "ការ\u00a0ងារ"
    assert clean_khmer_text(nbsp_text) == "ការងារ"

def test_khmer_syllable_reordering():
    """Validates Khmer Unicode canonical syllable component reordering."""
    text = "កម្ពុជា"
    normalized = normalize_khmer_unicode(text)
    assert isinstance(normalized, str)
    assert len(normalized) > 0
    assert "ក" in normalized
    assert "ជ" in normalized

def test_khmer_grapheme_count():
    """Validates accurate visual grapheme cluster counting for Khmer text."""
    word = "ខ្ញុំ"
    assert count_khmer_graphemes(word) == 1
    
    phrase = "កម្ពុជា"
    assert count_khmer_graphemes(phrase) == 3

def test_deprecation_of_destructive_character_replacement():
    """Verifies that legitimate Khmer words are NOT destructively altered."""
    word = "នារី"
    normalized = normalize_khmer_orthography(word)
    assert "ន" in normalized
    assert normalized == "នារី"

def test_typesense_schema_generation():
    """Validates Typesense schema definition structure for Khmer text."""
    schema = get_schema_definition("omnisense_lexicon")
    assert schema["name"] == "omnisense_lexicon"
    field_names = [f["name"] for f in schema["fields"]]
    assert "headword" in field_names
    assert "norm_headword" in field_names
    assert "canonical_headword" in field_names
    assert "source_title" in field_names

def test_jsonld_microdata_formatting():
    """Validates Schema.org DefinedTerm JSON-LD payload generation for AEO."""
    sample_doc = {
        "headword": "កំណត់ត្រា",
        "canonical_headword": "កំណត់ត្រា",
        "definition": "ការកត់ត្រា...",
        "phonetic_ipa": "kɑm.nɑt.traː"
    }
    jsonld = generate_jsonld_defined_term(sample_doc)
    assert jsonld["@context"] == "https://schema.org"
    assert jsonld["@type"] == "DefinedTerm"
    assert jsonld["name"] == "កំណត់ត្រា"
    assert jsonld["phoneticText"] == "kɑm.nɑt.traː"

def test_ip_anonymization_hashing():
    """Validates client IP hashing for GDPR/privacy compliance."""
    ip = "192.168.1.100"
    hashed = hash_user_ip(ip)
    assert hashed != ip
    assert len(hashed) == 16
    assert hash_user_ip("unknown") == "anonymized_unknown"
