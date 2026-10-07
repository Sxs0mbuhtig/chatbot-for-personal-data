from typing import Optional, List
from pydantic import BaseModel, Field


class MorphologicalAnalysis(BaseModel):
    root_morpheme: str = Field(..., description="Canonical root or base form")
    infix_type: Optional[str] = Field(None, description="Detected infix e.g. -n-, -m-, -b-")
    subscript_sequence: List[str] = Field(default_factory=list, description="Detected coeng/ជើង structures")
    register_shift: Optional[str] = Field(None, description="A-to-O or O-to-A series modification label")


class EtymologyDetail(BaseModel):
    origin_language: str = Field(..., description="Pali, Sanskrit, Proto-Mon-Khmer, French, Chinese, etc.")
    original_script: Optional[str] = Field(None, description="Original script representation (e.g., Devanagari)")
    root_meaning: Optional[str] = Field(None, description="Etymological meaning of the root morpheme")


class PhoneticsIPA(BaseModel):
    ipa_canonical: str = Field(..., description="Canonical IPA string e.g. /lɨː/")
    register: str = Field(..., description="First Register (Head-voice) or Second Register (Chest-voice)")


class OrthographicAlignment(BaseModel):
    chuon_nath_standard: str = Field(..., description="Canonical 1967 Chuon Nath dictionary spelling")
    vannsak_reform_variant: Optional[str] = Field(None, description="Keng Vannsak minimalist reform spelling variant")
    modern_colloquial_phonetic: Optional[str] = Field(None, description="Modern texting/informal phonetic spelling")
    dispute_notes_km: Optional[str] = Field(None, description="Explanation of orthographic controversy/evolution")


class LinguisticAnalysis(BaseModel):
    morphology: Optional[MorphologicalAnalysis] = None
    etymology: Optional[EtymologyDetail] = None
    phonetics: Optional[PhoneticsIPA] = None
    orthography: Optional[OrthographicAlignment] = None

class UsageRegister(BaseModel):
    is_taboo_or_vulgar: bool = False
    is_anatomical: bool = False
    formal_alternative_km: Optional[str] = None  # e.g., mapping to Pali/Sanskrit formal terms
    register_note_km: Optional[str] = None       # e.g., "ពាក្យអសុរោះ ប្រប្រើប្រាស់ក្នុងភាសានិយាយ"
