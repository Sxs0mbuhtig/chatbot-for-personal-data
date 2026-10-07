import re
import json
import time
import unicodedata2 as unicodedata
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from khmer_normalizer import (
    clean_khmer_text,
    extract_echo_roots,
    get_independent_vowel_variants,
    KHMER_LEK_TO
)

# =====================================================================
# CONSTANTS & PHONETIC MAPPING DICTIONARIES
# =====================================================================

COENG = "\u17d2"  # ជើង

# Strict Phonetic Alternation Sets 
# (ចំណាំ៖ «រ» ត្រូវរក្សាទុកដាច់ដោយឡែកពី «ល» និង «ឡ» ព្រោះក្នុងអក្ខរាវិរុទ្ធខ្មែរ មិនអនុញ្ញាតឱ្យប្តូរជំនួសគ្នាដាច់ខាត)
ALTERNATION_SETS = [
    {"ល", "ឡ"},  # เฉพาะ ល និង ឡ ដែលអាចជួបប្រទះការសរសេរច្រឡំគ្នាក្នុងការប្រើប្រាស់ជាក់ស្តែង
    {"ក", "គ"},
    {"ច", "ជ"},
    {"ត", "ទ"},
    {"ប", "ព"},
]

# Consonant Shifters (Muasikadonta / Treisap)
CONSONANT_SHIFTERS = {"\u17c9", "\u17ca"}  # ៉ , ៊

# Register Detection Patterns
FRANCO_PATTERNS = [
    r".*ស្ដ$", r".*ត៍$", r".*ហ្វ$", r".*ឡូ$", r".*ណាល់$", r"^ស៊ីញ៉េ$", r"^ស៊ីញេ$", r"^កូដ$"
]

ENGLO_PATTERNS = [
    r".*ហ្វ្លូ.*", r".*ស្ដារ.*", r".*ប្រូ.*", r".*ហ៊ីត.*"
]

PHONETIC_MODERN_PATTERNS = [
    r".*លឺ.*", r".*រលឹក.*", r".*រំលឹក.*", r".*រឹស.*"
]

FORMAL_CLASSICAL_PATTERNS = [
    r".*ឮ.*", r".*រឭក.*", r".*ឫស.*"
]

KNOWN_EXPRESSIVES = {"ឡេឡឺ", "ង៉ុក", "ង៉ុក", "ក្រង៉ុក", "ង៉ក់", "ង៉ឺតង៉ក់","ង៉ឺតង៉ត","តេងតាង","ប៉េតប៉ត" ,"ត្រេតត្រត", "ងាក់ងើ","ងីងើ", "ឡឺកី"}

# =====================================================================
# PYDANTIC DATA BOUNDARY SCHEMAS
# =====================================================================
class LinguisticContext(BaseModel):
    # Rename or alias the field to avoid shadowing BaseModel.register
    register_type: Optional[str] = Field(default=None, alias="register")
    
class RegisterAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    primary_register: str = Field(..., description="Primary detected register category")
    detected_registers: List[str] = Field(default_factory=list)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    etymology_type: str = Field(..., description="Language or structural origin")

class LinguisticContext(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=(), populate_by_name=True)
    register: str = Field(..., description="Linguistic register category")
    etymology_type: str = Field(default="native_km")
    boundary_note_km: str = Field(default="")
    educational_explanation_km: str = Field(default="")

class ExpressiveDigestionResult(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    input_raw: str
    normalized_root: str
    has_repetition: bool
    phonetic_variants: List[str]
    echo_roots: List[str]
    register_analysis: RegisterAnalysis
    linguistic_context: LinguisticContext
    resolved_entry: Optional[Dict[str, Any]] = None
    is_known_term: bool = False

class TypesenseDocumentSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    headword: str
    norm_headword: str
    canonical_headword: str
    pos: str = "កិ.គុ."
    register: str = "colloquial"
    definition: str
    synonyms: List[str] = Field(default_factory=list)
    phonetic_variants: List[str] = Field(default_factory=list)
    is_official_chuon_nath: bool = False
    source_title: str = "Khmer Modern Living Lexicon"
    sort_index: int = 0

# =====================================================================
# CORE INTELLIGENT DIGESTER CLASS
# =====================================================================

class KhmerExpressiveEngine:
    def __init__(self, known_lexicon_db: Optional[Dict[str, Dict[str, Any]]] = None):
        self.lexicon_db = known_lexicon_db or {}
        self.unknown_telemetry: Dict[str, int] = {}

    def clean_text(self, text: str) -> str:
        """Normalizes Unicode (NFC) and strips invisible boundary chars."""
        return clean_khmer_text(text)

    def strip_lek_to(self, text: str) -> str:
        """Strips trailing Lek To (ៗ) and whitespace."""
        return re.sub(r"[\s\u17d7]+$", "", self.clean_text(text)).strip()

    def generate_phonetic_variants(self, text: str, max_variants: int = 10) -> List[str]:
        """
        Generates phonetic variations based strictly on permitted modern/colloquial sets
        (such as ល <-> ឡ, independent vowels, and consonant shifters), keeping 'រ' strictly independent.
        Results are capped by max_variants to avoid Typesense index amplification.
        """
        clean = self.strip_lek_to(self.clean_text(text))
        variants = {clean}

        # 1. Independent Vowel Classical <-> Modern Bridging
        for iv_var in get_independent_vowel_variants(clean):
            variants.add(iv_var)

        # 2. Handle Strict Alternations (ល <-> ឡ, etc., excluding 'រ')
        for group in ALTERNATION_SETS:
            for char in group:
                if char in clean:
                    for target in group:
                        if target != char:
                            variants.add(clean.replace(char, target))

        # 3. Handle Consonant Shifter Variations (៊ vs ៉)
        for v in list(variants):
            if "\u17c9" in v:  # ៉ -> ៊
                variants.add(v.replace("\u17c9", "\u17ca"))
            if "\u17ca" in v:  # ៊ -> ៉
                variants.add(v.replace("\u17ca", "\u17c9"))

        # 4. Re-apply independent vowel variants across generated phonetic variants
        for v in list(variants):
            for iv in get_independent_vowel_variants(v):
                variants.add(iv)

        # Capped to max_variants to prevent index payload bloat
        res = list(variants)
        if clean in res:
            res.remove(clean)
            res.insert(0, clean)
        return res[:max_variants]

    def detect_register_and_etymology(self, word: str) -> RegisterAnalysis:
        """
        Detects loanword influences, classical dictionary standards, modern reforms, and expressives.
        """
        clean = self.clean_text(word)
        has_lek_to = KHMER_LEK_TO in clean
        root = self.strip_lek_to(clean)

        categories = []
        confidence = 0.5
        etymology_type = "Classical Khmer"

        # 1. Franco-Khmer Loanword Check (Technical, Legal, Daily)
        for pattern in FRANCO_PATTERNS:
            if re.search(pattern, root):
                categories.append("franco_khmer_loanword")
                confidence = 0.85
                etymology_type = "French Loanword"
                break

        # 2. Km-English Rap/Urban/Tech Loanword Check
        if not categories:
            for pattern in ENGLO_PATTERNS:
                if re.search(pattern, root):
                    categories.append("km_english_fusion")
                    confidence = 0.85
                    etymology_type = "English Loanword"
                    break

        # 3. Formal Classical Standard Check (Chuon Nath)
        if not categories:
            for pattern in FORMAL_CLASSICAL_PATTERNS:
                if re.search(pattern, root):
                    categories.append("formal_classical")
                    confidence = 0.8
                    etymology_type = "Classical Chuon Nath Standard"
                    break

        # 4. Phonetic Modern Standard Check (Keng Vannsak reform)
        if not categories:
            for pattern in PHONETIC_MODERN_PATTERNS:
                if re.search(pattern, root):
                    categories.append("phonetic_modern")
                    confidence = 0.8
                    etymology_type = "Post-Reform Simplified Spelling"
                    break

        # 5. Expressive / Onomatopoeia Check (Reduplicated or trailing Lek To ៗ)
        if not categories:
            echo_roots = extract_echo_roots(word)
            if has_lek_to or root in KNOWN_EXPRESSIVES or len(echo_roots) > 1:
                categories.append("expressive_onomatopoeia")
                confidence = 0.85
                etymology_type = "Expressive Onomatopoeia"

        if not categories:
            categories.append("colloquial_general")
            etymology_type = "Colloquial Khmer"

        return RegisterAnalysis(
            primary_register=categories[0],
            detected_registers=categories,
            confidence_score=min(confidence, 1.0),
            etymology_type=etymology_type
        )

    def build_linguistic_context(self, word: str, register_meta: RegisterAnalysis) -> LinguisticContext:
        """
        Builds user-facing educational context and historical notes.
        """
        primary = register_meta.primary_register
        
        boundary_notes = {
            "expressive_onomatopoeia": "ទម្រង់ពាក្យសូរឧបមា/ពិពណ៌នាមាយាទ រក្សាទម្រង់ស្ទួន ឬសញ្ញាលេខទោ (ៗ)។",
            "formal_classical": "អក្ខរាវិរុទ្ធផ្លូវការតាមវចនានុក្រមសម្តេចព្រះសង្ឃរាជ ជួន ណាត (បុរាណទម្រង់)។",
            "phonetic_modern": "ទម្រង់អក្ខរាវិរុទ្ធសម្រួលតាមបែបសម្លេងនិយាយទំនើប (ចលនាបណ្ឌិត កេង វ៉ាន់សាក់)។",
            "franco_khmer_loanword": "ពាក្យកម្ចីពីភាសាបារាំង ប្រើប្រាស់ក្នុងវិស័យរដ្ឋបាល ច្បាប់ ឬបច្ចេកទេស។",
            "km_english_fusion": "ពាក្យកម្ចី ឬពាក្យស្លែងទំនើបបែបតន្ត្រី Rap/Urban ពីភាសាអង់គ្លេស។",
            "colloquial_general": "ទម្រង់ពាក្យទូទៅក្នុងភាសាខ្មែរ។"
        }

        educational_explanations = {
            "expressive_onomatopoeia": f"ពាក្យ «{word}» ជានាមសព្ទ/កិរិយាសព្ទពិពណ៌នាសូរ ឬអាការ។",
            "formal_classical": f"ពាក្យ «{word}» ជាទម្រង់ដើមតាមវចនានុក្រមជួនណាត។",
            "phonetic_modern": f"ពាក្យ «{word}» ជាទម្រង់សរសេរតាមសម្លេងអានទំនើប។",
            "franco_khmer_loanword": f"ពាក្យ «{word}» ជាពាក្យក្លាយមកពីភាសាបារាំង។",
            "km_english_fusion": f"ពាក្យ «{word}» ជាពាក្យស្លែង/បច្ចេកសព្ទក្លាយមកពីភាសាអង់គ្លេស។",
            "colloquial_general": f"ពាក្យ «{word}» ប្រើប្រាស់ក្នុងទម្រង់និយាយទូទៅ។"
        }

        return LinguisticContext(
            register=primary,
            etymology_type=register_meta.etymology_type,
            boundary_note_km=boundary_notes.get(primary, boundary_notes["colloquial_general"]),
            educational_explanation_km=educational_explanations.get(primary, educational_explanations["colloquial_general"])
        )

    def digest_input(self, raw_input: str) -> ExpressiveDigestionResult:
        """
        Main digestion pipeline. Analyzes register, generates phonetic bridges,
        extracts echo roots, and constructs strict Pydantic result.
        """
        cleaned = self.clean_text(raw_input)
        has_lek_to = KHMER_LEK_TO in cleaned
        root_term = self.strip_lek_to(cleaned)

        phonetic_variants = self.generate_phonetic_variants(root_term)
        echo_roots = extract_echo_roots(cleaned)
        register_meta = self.detect_register_and_etymology(cleaned)
        ling_context = self.build_linguistic_context(cleaned, register_meta)

        matched_entry = None
        for variant in phonetic_variants:
            if variant in self.lexicon_db:
                matched_entry = self.lexicon_db[variant]
                break

        if not matched_entry and root_term in self.lexicon_db:
            matched_entry = self.lexicon_db[root_term]

        return ExpressiveDigestionResult(
            input_raw=raw_input,
            normalized_root=root_term,
            has_repetition=has_lek_to,
            phonetic_variants=phonetic_variants,
            echo_roots=echo_roots,
            register_analysis=register_meta,
            linguistic_context=ling_context,
            resolved_entry=matched_entry,
            is_known_term=matched_entry is not None
        )

def is_invalid_definition(def_text: str) -> bool:
    """
    ពិនិត្យមើលថាតើនិយមន័យទទេ ឬមានតែសញ្ញាខណ្ឌ/ចន្លោះទំនេរ/IPA ឬទេ។
    """
    if not def_text:
        return True
    
    # លុបចន្លោះទំនេរ និមិត្តសញ្ញាមើលមិនឃើញ និងសញ្ញាខណ្ឌ
    cleaned = re.sub(r"[\s\u17d4\u200b\u00a0]+", "", def_text)
    
    # ប្រសិនបើគ្មានអក្សរសេសសល់ ឬមានតែសញ្ញាខណ្ឌ ຖືថា Invalid
    return len(cleaned) == 0

def sanitize_definition(def_text: str, fallback_text: str = "") -> str:
    """
    សម្អាតនិយមន័យ និងផ្លាស់ប្តូរទៅប្រើ Fallback ប្រសិនបើស្វែងរកឃើញតែសញ្ញាខណ្ឌ។
    """
    if is_invalid_definition(def_text):
        return fallback_text
    
    # លុបសញ្ញាខណ្ឌដែលនៅដើមអត្ថបទ (បើមាន)
    cleaned = re.sub(r"^[\s\u17d4\u200b\u00a0]+", "", def_text).strip()
    return cleaned

# Global singleton instance
expressive_engine = KhmerExpressiveEngine()
def build_typesense_payload(entry_data: Dict[str, Any], engine: Optional[KhmerExpressiveEngine] = None) -> Optional[Dict[str, Any]]:
    """
    Transforms raw entries into fully bridged, searchable documents for Typesense.
    Rejects or cleans empty/punct-only definitions across the lexicon.
    """
    eng = engine or expressive_engine
    root = eng.strip_lek_to(entry_data.get("headword", ""))
    raw_def = entry_data.get("definition", "")

    # ប្រសិនបើនិយមន័យមានតែសញ្ញាខណ្ឌ «។» ឬទទេរ ត្រូវបដិសេធ (ឬកំណត់ fallback)
    cleaned_def = sanitize_definition(raw_def)
    if not cleaned_def:
        # បើចង់រំលង Entry ខូច៖
        return None 

    phonetic_variants = eng.generate_phonetic_variants(root, max_variants=10)[:10]
    raw_synonyms = entry_data.get("synonyms", [])
    deduped_synonyms = list(set(raw_synonyms))
    
    return {
        "headword": entry_data.get("headword", ""),
        "norm_headword": root,
        "canonical_headword": entry_data.get("canonical_headword", root),
        "pos": entry_data.get("pos", "កិ.គុ."),
        "register": entry_data.get("register", "colloquial"),
        "definition": cleaned_def,
        "synonyms": deduped_synonyms,
        "phonetic_variants": phonetic_variants,
        "is_official_chuon_nath": entry_data.get("is_official_chuon_nath", False),
        "source_title": entry_data.get("source_title", "Khmer Modern Living Lexicon"),
        "sort_index": entry_data.get("sort_index", int(time.time()))
    }
