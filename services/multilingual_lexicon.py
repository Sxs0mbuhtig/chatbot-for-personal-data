from typing import Dict, List, Optional
from pydantic import BaseModel

class TranslationEntry(BaseModel):
    anchor_en: str
    translations: Dict[str, str]  # km, th, lo, vi

class MultilingualLexiconService:
    def __init__(self):
        # Anchor-based dictionary mapping English to Khmer, Thai, Lao, Vietnamese
        self._lexicon_db: Dict[str, Dict[str, str]] = {
            "computer": {
                "en": "computer",
                "km": "កុមព្យូទ័រ",
                "th": "คอมพิวเตอร์",
                "lo": "คอมพิวเตอร์",
                "vi": "máy tính"
            },
            "network": {
                "en": "network",
                "km": "បណ្តាញ",
                "th": "เครือข่าย",
                "lo": "ເຄືອຂ່າຍ",
                "vi": "mạng lưới"
            },
            "security": {
                "en": "security",
                "km": "សុវត្ថិភាព",
                "th": "ความปลอดภัย",
                "lo": "ຄວາມປອດໄພ",
                "vi": "bảo mật"
            }
        }

    def get_translation(self, term: str, target_lang: str) -> Optional[str]:
        """Retrieve translation for a term in a target language using English anchor."""
        term_lower = term.lower().strip()
        
        # Check direct anchor match
        if term_lower in self._lexicon_db:
            entry = self._lexicon_db[term_lower]
            return entry.get(target_lang)
            
        # Search across all language values
        for anchor, langs in self._lexicon_db.items():
            if term_lower in langs.values():
                return langs.get(target_lang)
                
        return None

    def get_all_translations(self, term: str) -> Optional[Dict[str, str]]:
        """Retrieve translations across all 5 supported languages."""
        term_lower = term.lower().strip()
        if term_lower in self._lexicon_db:
            return self._lexicon_db[term_lower]
            
        for anchor, langs in self._lexicon_db.items():
            if term_lower in langs.values():
                return langs
                
        return None

    def add_entry(self, anchor_en: str, translations: Dict[str, str]) -> None:
        """Add a new multilingual lexicon entry."""
        self._lexicon_db[anchor_en.lower().strip()] = {
            "en": anchor_en,
            **{k: v for k, v in translations.items() if k in {"km", "th", "lo", "vi"}}
        }
