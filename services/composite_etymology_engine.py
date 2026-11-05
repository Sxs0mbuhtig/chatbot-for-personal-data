import re
import sqlite3
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from khmer_normalizer import (
    clean_khmer_text,
    extract_echo_roots
)

DB_PATH = "chuon_nath_fts.db"

# Expanded Loanword & Etymology Patterns with Sub-classifications
LOANWORD_PATTERNS = {
    "pali_sanskrit": [
        r".*កិច្ច.*", r".*ដ្ឋាន.*", r".*ធម៌.*", r".*សាសនា.*", r".*ប្រយោជន៍.*", r".*វិជ្ជា.*",
        r".*សន្តិ.*", r".*មន្រ្តី.*", r".*រដ្ឋ.*", r".*បុរី.*", r".*មហា.*", r".*សិក្សា.*", r".*វិទ្យា.*"
    ],
    "french": [
        r".*ស្ដ$", r".*ត៍$", r".*ហ្វ$", r".*ឡូ$", r".*ណាល់$", r"^ស៊ីញ៉េ$", r"^ស៊ីញេ$", r"^កូដ$",
        r".*កាហ្វេ.*", r".*ប៉ូលិស.*", r".*ស៊ុប.*", r".*កាត.*", r".*បេតុង.*", r".*សាកុប.*"
    ],
    "english": [
        r".*ហ្វ្លូ.*", r".*ស្ដារ.*", r".*ប្រូ.*", r".*ហ៊ីត.*", r".*កុំព្យូទ័រ.*", r".*អ៊ីនធឺណិត.*",
        r".*ស្មាតហ្វូន.*", r".*អាប.*", r".*វ៉ិប.*", r".*ប្លុក.*", r".*សូហ្វវែរ.*"
    ],
    "thai": [
        r".*ឡាន.*", r".*ឆៃហ្វុង.*", r".*ហៀង.*", r".*ទែន.*"
    ],
    "vietnamese": [
        r".*ហ៊ុយទីវ.*", r".*កាហ្វេ.*", r".*ណែម.*"
    ],
    "chinese": [
        r".*តៅហ៊ូ.*", r".*មី.*", r".*ឆា.*", r".*ប៉ាវ.*", r".*ចែ.*", r".*លក់.*"
    ]
}

# Morphological Affixes & Infixes in Khmer
DERIVATIONAL_AFFIXES = {
    "prefixes": [r"^ដំណ", r"^បំ", r"^កម", r"^អប", r"^អទ", r"^បញ្", r"^ប្រ"],
    "infixes": [r"[\u1780-\u17b3]\u17d2[\u1780-\u17b3]?[\u17c6\u17b6-\u17d3]"],  # Nominalizing/causative infix markers
    "suffixes": [r"ភាព$", r"ការ$", r"និយម$"]
}

class MorphologicalBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    prefix: Optional[str] = None
    root: str
    suffix: Optional[str] = None
    infix_markers: List[str] = Field(default_factory=list)

class ComponentBreakdown(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    component: str = Field(..., description="Constituent component or root syllable")
    is_in_dictionary: bool = Field(False, description="Whether component exists in local dictionary")
    definition: Optional[str] = Field(None, description="Definition of constituent component if matched")
    morphology: Optional[MorphologicalBreakdown] = None

class LoanwordEtymology(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    etymology_class: str = Field(..., description="pali_sanskrit, french, english, thai, vietnamese, chinese, or native_km")
    origin_language_label: str = Field(..., description="Human-readable origin language label")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_markers: List[str] = Field(default_factory=list)

class OrthographicAlignmentNotes(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    chuon_nath_standard: str = Field(..., description="Chuon Nath standard form or commentary")
    vannsak_reform_variant: Optional[str] = Field(None, description="Post-reform Keng Vannsak simplified variant if applicable")
    modern_colloquial_usage: str = Field(..., description="Modern usage notes")
    historical_notes_km: str = Field(..., description="Detailed historical and orthographic comparison in Khmer")

class CompositeEtymologyResult(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    raw_term: str
    normalized_term: str
    is_composite: bool
    compound_type: str = Field("endocentric", description="endocentric (head-modifier) or exocentric (bahuvrihi/idiomatic)")
    head_component: Optional[str] = Field(None, description="Grammatical head of the compound")
    components: List[ComponentBreakdown] = Field(default_factory=list)
    etymology: LoanwordEtymology
    orthographic_notes: OrthographicAlignmentNotes

DOMAIN_PATTERNS = {
    "military_defense": [r".*ទ័ព.*", r".*កង.*", r".*សឹក.*", r".*យោធា.*", r".*អាវុធ.*", r".*យុទ្ធ.*", r".*សមរភូម.*", r".*បញ្ជាការ.*"],
    "legal_governance": [r".*ច្បាប់.*", r".*តុលាការ.*", r".*រដ្ឋបាល.*", r".*ក្រសួង.*", r".*សិទ្ធិ.*", r".*អាជ្ញា.*", r".*បញ្ញត្តិ.*", r".*សន្ធិសញ្ញា.*"],
    "geography_nature": [r".*ភ្នំ.*", r".*ទន្លេ.*", r".*ស្ទឹង.*", r".*សមុទ្រ.*", r".*ព្រៃ.*", r".*កោះ.*", r".*ខេត្ត.*", r".*ក្រុង.*", r".*ដី.*"],
    "mechanical_technology": [r".*ម៉ាស៊ីន.*", r".*កុំព្យូទ័រ.*", r".*ទូរស័ព្ទ.*", r".*អគ្គិសនី.*", r".*យន្ត.*", r".*បច្ចេកវិទ្យា.*", r".*សាយប័រ.*"],
    "anatomy_health": [r".*ដៃ.*", r".*ជើង.*", r".*ក្បាល.*", r".*ភ្នែក.*", r".*បេះដូង.*", r".*ជំងឺ.*", r".*ថ្នាំ.*", r".*ពេទ្យ.*"],
    "culinary_gastronomy": [r".*នំ.*", r".*បាយ.*", r".*ស៊ុប.*", r".*ម្ហូប.*", r".*ទឹក.*", r".*សាច់.*", r".*កាហ្វេ.*"]
}

DOMAIN_LABELS = {
    "military_defense": "យោធា និង ការពារជាតិ (Military & Defense)",
    "legal_governance": "ច្បាប់ និង រដ្ឋបាល (Legal & Governance)",
    "geography_nature": "ភូមិសាស្ត្រ និង ធម្មជាតិ (Geography & Nature)",
    "mechanical_technology": "មេកានិច និង បច្ចេកវិទ្យា (Mechanical & Technology)",
    "anatomy_health": "រូបរាងកាយ និង សុខភាព (Anatomy & Health)",
    "culinary_gastronomy": "ម្ហូបអាហារ និង ចំណីអាហារ (Culinary & Gastronomy)",
    "general": "ពាក្យទូទៅ (General Lexicon)"
}

class KhmerCompositeEtymologyEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def classify_domain_taxonomy(self, term: str, definition: str = "") -> str:
        clean = clean_khmer_text(term)
        combined = f"{clean} {definition}"
        for dom, patterns in DOMAIN_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, combined):
                    return dom
        return "general"

    def get_domain_label(self, domain_key: str) -> str:
        return DOMAIN_LABELS.get(domain_key, DOMAIN_LABELS["general"])

    def _check_db_exact(self, term: str) -> Optional[str]:
        if not os.path.exists(self.db_path) or not term:
            return None
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT definition FROM dictionary
                WHERE norm_headword = ? OR headword = ?
                LIMIT 1
                """,
                (term, term)
            )
            row = cursor.fetchone()
            if row and row[0]:
                return row[0].strip()
            return None
        except Exception:
            return None
        finally:
            if conn:
                conn.close()

    def _split_into_graphemes(self, text: str) -> List[str]:
        pattern = r"\u17d7|[\u1780-\u17b3][\u17c9\u17ca]?(?:\u17d2[\u1780-\u17b3])*(?:[\u17b6-\u17c5])*(?:[\u17c6-\u17d3])*|[^\u1780-\u17b3]"
        return [c for c in re.findall(pattern, text) if c.strip()]

    def segment_bimm(self, text: str, max_word_graphemes: int = 6) -> List[str]:
        clean = clean_khmer_text(text)
        if not clean:
            return []
        graphemes = self._split_into_graphemes(clean)
        if not graphemes:
            return [clean]
        n = len(graphemes)

        fmm_tokens = []
        i = 0
        while i < n:
            matched_len = 1
            for l in range(min(max_word_graphemes, n - i), 0, -1):
                candidate = "".join(graphemes[i : i + l])
                if self._check_db_exact(candidate) is not None:
                    matched_len = l
                    break
            fmm_tokens.append("".join(graphemes[i : i + matched_len]))
            i += matched_len

        bmm_tokens = []
        i = n
        while i > 0:
            matched_len = 1
            for l in range(min(max_word_graphemes, i), 0, -1):
                candidate = "".join(graphemes[i - l : i])
                if self._check_db_exact(candidate) is not None:
                    matched_len = l
                    break
            bmm_tokens.insert(0, "".join(graphemes[i - matched_len : i]))
            i -= matched_len

        if fmm_tokens == bmm_tokens:
            return fmm_tokens

        if len(fmm_tokens) < len(bmm_tokens):
            return fmm_tokens
        elif len(bmm_tokens) < len(fmm_tokens):
            return bmm_tokens

        fmm_unknowns = sum(1 for t in fmm_tokens if self._check_db_exact(t) is None)
        bmm_unknowns = sum(1 for t in bmm_tokens if self._check_db_exact(t) is None)
        return fmm_tokens if fmm_unknowns <= bmm_unknowns else bmm_tokens

    def analyze_morphology(self, component: str) -> MorphologicalBreakdown:
        """Extracts derivational prefixes, suffixes, and root forms from a lexical component."""
        prefix = None
        suffix = None
        root = component

        for p in DERIVATIONAL_AFFIXES["prefixes"]:
            if re.search(p, root):
                match = re.search(p, root)
                if match:
                    prefix = match.group(0)
                    root = root[len(prefix):]
                    break

        for s in DERIVATIONAL_AFFIXES["suffixes"]:
            if re.search(s, root):
                match = re.search(s, root)
                if match:
                    suffix = match.group(0)
                    root = root[:-len(suffix)]
                    break

        return MorphologicalBreakdown(prefix=prefix, root=root, suffix=suffix)

    def decompose_composite(self, term: str) -> List[ComponentBreakdown]:
        clean = clean_khmer_text(term)
        echo_roots = extract_echo_roots(clean)
        roots = echo_roots if len(echo_roots) > 1 else self.segment_bimm(clean)

        components: List[ComponentBreakdown] = []
        for r in roots:
            d = self._check_db_exact(r)
            morph = self.analyze_morphology(r)
            components.append(
                ComponentBreakdown(
                    component=r,
                    is_in_dictionary=d is not None,
                    definition=d,
                    morphology=morph
                )
            )
        return components

    def detect_loanword_etymology(self, term: str) -> LoanwordEtymology:
        clean = clean_khmer_text(term)
        matched_markers = []

        for etype, patterns in LOANWORD_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, clean):
                    matched_markers.append(pat)
                    labels = {
                        "pali_sanskrit": "ភាសាបាលី-សំស្ក្រឹត (Pali / Sanskrit)",
                        "french": "ភាសាបារាំង (French Loanword)",
                        "english": "ភាសាអង់គ្លេស (English Loanword)",
                        "thai": "ភាសាថៃ (Thai Loanword)",
                        "vietnamese": "ភាសាវៀតណាម (Vietnamese Loanword)",
                        "chinese": "ភាសាចិន (Chinese Loanword)"
                    }
                    confidence = min(0.95, 0.75 + (0.05 * len(matched_markers)))
                    return LoanwordEtymology(
                        etymology_class=etype,
                        origin_language_label=labels.get(etype, etype),
                        confidence=confidence,
                        evidence_markers=matched_markers
                    )

        return LoanwordEtymology(
            etymology_class="native_km",
            origin_language_label="ភាសាខ្មែរដើម (Native Mon-Khmer)",
            confidence=0.88,
            evidence_markers=["native_mon_khmer_morphology"]
        )

    def classify_compound_structure(self, components: List[ComponentBreakdown]) -> tuple[str, Optional[str]]:
        """Classifies whether the compound is endocentric (head noun first or last) and identifies the head."""
        if len(components) <= 1:
            return "simple", components[0].component if components else None
        
        # In Khmer nominal compounds, the grammatical head is typically the first constituent (Left-Headed)
        head = components[0].component
        return "endocentric", head

    def generate_orthographic_alignment(self, term: str, etymology: LoanwordEtymology) -> OrthographicAlignmentNotes:
        clean = clean_khmer_text(term)
        eclass = etymology.etymology_class

        if eclass == "pali_sanskrit":
            cn_std = f"អក្ខរាវិរុទ្ធបុរាណតាមវចនានុក្រមជួន ណាត រក្សាឫសបាលី-សំស្ក្រឹត «{clean}»"
            vannsak = "ទម្រង់សម្រួលអក្ខរាវិរុទ្ធទំនើប"
            modern = "ប្រើប្រាស់ក្នុងភាសាផ្លូវការ រដ្ឋបាល និងអក្សរសាស្ត្រ"
            notes = "ប្រៀបធៀប៖ វចនានុក្រម ជួន ណាត រក្សាទម្រង់ដើមបាលី-សំស្ក្រឹត ឯចលនា កេង វ៉ាន់សាក់ សម្រួលតាមសូរសំឡេងអាន។"
        elif eclass in ("french", "english"):
            cn_std = f"ពាក្យកម្ចីបច្ចឹមប្រទេស «{clean}» មិនមានក្នុងវចនានុក្រមជួនណាត ១៩៦៧"
            vannsak = None
            modern = "ពាក្យកម្ចីប្រើប្រាស់ទូលំទូលាយក្នុងបច្ចេកវិទ្យា និងជីវភាពប្រចាំថ្ងៃ"
            notes = f"ពាក្យ «{clean}» ជាពាក្យកម្ចីពី {etymology.origin_language_label} ដែលត្រូវបានកត់ត្រាក្នុងវចនានុក្រមទំនើប។"
        else:
            cn_std = f"អក្ខរាវិរុទ្ធផ្លូវការតាមវចនានុក្រម ជួន ណាត «{clean}»"
            vannsak = "ទម្រង់សរសេរតាមសំឡេង"
            modern = "ប្រើប្រាស់ក្នុងទម្រង់និយាយ និងសរសេរទូទៅ"
            notes = f"ទម្រង់ «{clean}» ស្របតាមស្តង់ដារអក្ខរាវិរុទ្ធខ្មែរដើម។"

        return OrthographicAlignmentNotes(
            chuon_nath_standard=cn_std,
            vannsak_reform_variant=vannsak,
            modern_colloquial_usage=modern,
            historical_notes_km=notes
        )

    def analyze_term(self, term: str) -> CompositeEtymologyResult:
        clean = clean_khmer_text(term)
        components = self.decompose_composite(clean)
        is_composite = len(components) > 1 or (len(components) == 1 and components[0].component != clean)
        
        compound_type, head_comp = self.classify_compound_structure(components)
        etymology = self.detect_loanword_etymology(clean)
        ortho_notes = self.generate_orthographic_alignment(clean, etymology)

        return CompositeEtymologyResult(
            raw_term=term,
            normalized_term=clean,
            is_composite=is_composite,
            compound_type=compound_type,
            head_component=head_comp,
            components=components,
            etymology=etymology,
            orthographic_notes=ortho_notes
        )

composite_etymology_engine = KhmerCompositeEtymologyEngine()
