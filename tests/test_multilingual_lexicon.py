import pytest
from services.multilingual_lexicon import MultilingualLexiconService

def test_multilingual_lexicon_full_coverage():
    service = MultilingualLexiconService()
    
    # Direct English anchor lookups
    assert service.get_translation("computer", "km") == "កុមព្យូទ័រ"
    assert service.get_translation("computer", "th") == "คอมพิวเตอร์"
    assert service.get_translation("computer", "lo") == "คอมพิวเตอร์"
    assert service.get_translation("computer", "vi") == "máy tính"
    
    # Reverse lookup using non-English terms (hits lines 49 & 57-61)
    assert service.get_translation("កុមព្យូទ័រ", "en") == "computer"
    assert service.get_translation("เครือข่าย", "en") == "network"
    
    # Get all translations via reverse lookup
    all_trans = service.get_all_translations("សុវត្ថិភាព")
    assert all_trans is not None
    assert all_trans["en"] == "security"
    
    # Missing term fallbacks
    assert service.get_translation("nonexistent", "en") is None
    assert service.get_all_translations("nonexistent") is None

    # Add entry branch
    service.add_entry("router", {
        "km": "រ៉ូទ័រ",
        "th": "เราเตอร์",
        "lo": "ເຣົາເຕີ",
        "vi": "router"
    })
    assert service.get_translation("រ៉ូទ័រ", "en") == "router"
