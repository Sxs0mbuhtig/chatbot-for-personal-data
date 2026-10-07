import re
import json
import time
import unicodedata2 as unicodedata
from typing import Dict, List, Any, Optional

# =====================================================================
# CONSTANTS & PHONETIC MAPPING DICTIONARIES
# =====================================================================

KHMER_LEK_TO = "\u17d7"  # ៗ
COENG = "\u17d2"        # ជើង

# Phonetic Alternation Sets (L/R Swaps, Glottal/Liquid variations)
ALTERNATION_SETS = [
    {"ល", "រ", "ឡ"},
    {"ក", "គ"},
    {"ច", "ជ"},
    {"ត", "ទ"},
    {"ប", "ព"},
]

# Consonant Shifters (Muasikadonta / Treisap)
CONSONANT_SHIFTERS = {"\u17c9", "\u17ca"}  # ៉ , ៊

# Loanword Register Heuristics
FRANCO_PATTERNS = [
    r".*ស្ដ$", r".*ត៍$", r".*ហ្វ$", r".*ឡូ$", r".*ណាល់$"
]

ENGLO_PATTERNS = [
    r".*ហ្វ្លូ.*", r".*ស្ដារ.*", r".*ប្រូ.*", r".*ហ៊ីត.*"
]

# =====================================================================
# CORE INTELLIGENT DIGESTER CLASS
# =====================================================================

class KhmerExpressiveEngine:
    def __init__(self, known_lexicon_db: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        In-memory lexicon store for demonstration. In production, this proxies
        to Typesense / PostgreSQL.
        """
        self.lexicon_db = known_lexicon_db or {}
        self.unknown_telemetry: Dict[str, int] = {}

    def clean_text(self, text: str) -> str:
        """Normalizes Unicode (NFC) and strips invisible boundary chars."""
        if not text:
            return ""
        text = unicodedata.normalize("NFC", text)
        text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)
        return re.sub(r"\s+", " ", text).strip()

    def strip_lek_to(self, text: str) -> str:
        """Strips trailing Lek To (ៗ) and whitespace."""
        return re.sub(r"[\s\u17d7]+$", "", text).strip()

    def generate_phonetic_variants(self, text: str) -> List[str]:
        """
        Generates phonetic variations for L/R swaps, shifter permutations,
        and common informal typing variants.
        """
        clean = self.strip_lek_to(self.clean_text(text))
        variants = {clean}

        # 1. Handle L/R and ឡ/រ/ល Alternations
        for group in ALTERNATION_SETS:
            for char in group:
                if char in clean:
                    for target in group:
                        if target != char:
                            variants.add(clean.replace(char, target))

        # 2. Handle Consonant Shifter Variations (៊ vs ៉)
        for v in list(variants):
            if "\u17c9" in v:  # ៉ -> ៊
                variants.add(v.replace("\u17c9", "\u17ca"))
            if "\u17ca" in v:  # ៊ -> ៉
                variants.add(v.replace("\u17ca", "\u17c9"))

        return list(variants)

    def detect_register_and_etymology(self, word: str) -> Dict[str, Any]:
        """
        Detects loanword influences, regional dialects, and expressives.
        """
        clean = self.clean_text(word)
        has_lek_to = KHMER_LEK_TO in clean
        root = self.strip_lek_to(clean)

        categories = []
        confidence = 0.5

        # Expressive / Onomatopoeia Check
        if has_lek_to or len(re.findall(r"[\u1780-\u17b3]", root)) <= 2:
            categories.append("expressive_onomatopoeia")
            confidence += 0.3

        # Franco-Khmer Loanword Check (Courtroom, Math, Law, Admin)
        for pattern in FRANCO_PATTERNS:
            if re.search(pattern, root):
                categories.append("franco_khmer_loanword")
                confidence += 0.25
                break

        # Km-English Rap/Urban/Tech Loanword Check
        for pattern in ENGLO_PATTERNS:
            if re.search(pattern, root):
                categories.append("km_english_fusion")
                confidence += 0.25
                break

        if not categories:
            categories.append("colloquial_general")

        return {
            "primary_register": categories[0],
            "detected_registers": categories,
            "confidence_score": min(confidence, 1.0)
        }

    def digest_input(self, raw_input: str) -> Dict[str, Any]:
        """
        Main digestion pipeline. Breaks down input, analyzes register,
        generates phonetic bridges, resolves canonical form, and tracks telemetry.
        """
        cleaned = self.clean_text(raw_input)
        has_lek_to = KHMER_LEK_TO in cleaned
        root_term = self.strip_lek_to(cleaned)
        
        # 1. Phonetic Bridging & Alternations
        phonetic_variants = self.generate_phonetic_variants(root_term)
        
        # 2. Register & Etymology Analysis
        register_meta = self.detect_register_and_etymology(cleaned)

        # 3. Lookup or Telemetry Flagging
        matched_entry = None
        for variant in phonetic_variants:
            if variant in self.lexicon_db:
                matched_entry = self.lexicon_db[variant]
                break

        # Log to Telemetry if unrecognized
        if not matched_entry:
            self.unknown_telemetry[root_term] = self.unknown_telemetry.get(root_term, 0) + 1

        # Build payload for feedback loop
        payload = {
            "input_raw": raw_input,
            "normalized_root": root_term,
            "has_repetition": has_lek_to,
            "phonetic_variants": phonetic_variants,
            "register_analysis": register_meta,
            "resolved_entry": matched_entry,
            "is_known_term": matched_entry is not None,
            "telemetry": {
                "flagged_for_ingestion": matched_entry is None,
                "hit_count": self.unknown_telemetry.get(root_term, 0)
            }
        }
        return payload


# =====================================================================
# BATCH SEEDING ENGINE & TYPESENSE CONNECTOR
# =====================================================================

def build_typesense_payload(entry_data: Dict[str, Any], engine: KhmerExpressiveEngine) -> Dict[str, Any]:
    """
    Transforms raw entries into fully bridged, searchable documents for Typesense.
    """
    root = engine.strip_lek_to(entry_data["headword"])
    phonetic_variants = engine.generate_phonetic_variants(root)
    
    # Combined synonyms and variants for search bridging
    all_synonyms = list(set(entry_data.get("synonyms", []) + phonetic_variants))
    
    return {
        "headword": entry_data["headword"],
        "norm_headword": root,
        "canonical_headword": entry_data.get("canonical_headword", root),
        "pos": entry_data.get("pos", "កិ.គុ."),
        "register": entry_data.get("register", "colloquial"),
        "definition": entry_data["definition"],
        "synonyms": all_synonyms,
        "phonetic_variants": phonetic_variants,
        "is_official_chuon_nath": entry_data.get("is_official_chuon_nath", False),
        "source_title": entry_data.get("source_title", "Khmer Modern Living Lexicon"),
        "sort_index": int(time.time())
    }

# Seed Dataset featuring Expressives, Franco-Khmer, and Km-English Rap Fusion
SEED_LEXICON_DATA = [
    # Expressives / Onomatopoeia
    {
        "headword": "ឡេឡឺ",
        "pos": "កិ.គុ.",
        "register": "expressive",
        "definition": "អាការធ្វើភ្នែកស្លឺៗ ឬធ្វើមិនដឹងមិនឮ ហាក់ដូចជាភ្លើៗអត់យល់ការណ៍។",
        "synonyms": ["ឡឺកី", "ឡឺៗ", "ភ្លើៗ"],
        "is_official_chuon_nath": False
    },
    {
        "headword": "តេងតាងៗ",
        "pos": "កិ.គុ.",
        "register": "expressive",
        "definition": "សូរ ឬអាការយោលចុះឡើង ទយតយ រ揺រអាក់ រកទប់លំនឹងមិនបាន។",
        "synonyms": ["ទយតយ", "តោងតាង"],
        "is_official_chuon_nath": False
    },
    # Franco-Khmer Influenced (Technical/Legal/Daily)
    {
        "headword": "ស៊ីញ៉េ",
        "pos": "កិ.",
        "register": "franco_khmer",
        "definition": "ចុះហត្ថលេខា (ក្លាយមកពីពាក្យបារាំង Signer)។",
        "synonyms": ["ចុះហត្ថលេខា", "ស៊ីញេ"],
        "is_official_chuon_nath": False
    },
    {
        "headword": "កូដ",
        "pos": "ន.",
        "register": "franco_khmer",
        "definition": "ក្រម ឬច្បាប់ (ក្លាយមកពីពាក្យបារាំង Code ដូចជា Code Criminel)។",
        "synonyms": ["ក្រម", "ច្បាប់"],
        "is_official_chuon_nath": False
    },
    # Km-English & Urban Rap Music Fusion
    {
        "headword": "ហ្វ្លូ",
        "pos": "ន./កិ.គុ.",
        "register": "km_english_fusion",
        "definition": "ជังหวៈ ឬលំហូរចង្វាក់នៃការច្រៀងរ៉ॅप (Flow)។",
        "synonyms": ["លំហូរ", "ចង្វាក់"],
        "is_official_chuon_nath": False
    },
    {
        "headword": "ប្រូ",
        "pos": "ន.",
        "register": "km_english_fusion",
        "definition": "ពាក្យអំពាវនាវហៅមិត្តភក្តិប្រុសៗដោយရင်းស្និទ្ធ (Bro / Brother)។",
        "synonyms": ["បងប្រុស", "ពួកម៉ាក"],
        "is_official_chuon_nath": False
    }
]

# =====================================================================
# DEMONSTRATION & RUNTIME TEST
# =====================================================================

if __name__ == "__main__":
    engine = KhmerExpressiveEngine()

    print("=== 1. DIGESTING BATCH SEED DATA WITH AUTOMATIC PHONETIC BRIDGING ===")
    prepared_documents = []
    for item in SEED_LEXICON_DATA:
        doc = build_typesense_payload(item, engine)
        prepared_documents.append(doc)
        # Register into local engine store
        engine.lexicon_db[doc["norm_headword"]] = doc

    print(f"Successfully processed {len(prepared_documents)} seed documents.")
    print(f"Sample Typesense Payload:\n{json.dumps(prepared_documents[0], ensure_ascii=False, indent=2)}\n")

    print("=== 2. TESTING INTELLIGENT INPUT DIGESTER ===")
    test_queries = [
        "រេឬ",        # L/R Swap variant of ឡេឡឺ
        "តេងតាងៗ",   # Expressive with Lek To
        "ស៊ីញេ",      # Franco-Khmer variant
        "ហ្វ្លូ",       # Km-English Rap term
        "ឡឺកីកី",     # Unregistered slang variation
    ]

    for q in test_queries:
        result = engine.digest_input(q)
        print(f"Query: '{q}'")
        print(f" -> Normalized Root: {result['normalized_root']}")
        print(f" -> Register: {result['register_analysis']['primary_register']}")
        print(f" -> Phonetic Bridges Generated: {result['phonetic_variants']}")
        print(f" -> Known Term Match: {result['is_known_term']}")
        if not result['is_known_term']:
            print(f" -> [TELEMETRY LOGGED] Flagged for Review (Hit Count: {result['telemetry']['hit_count']})")
        print("-" * 60)
