from typing import Optional, List, Any, Dict, Union
from pydantic import BaseModel, Field, ConfigDict


class SearchResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    id: str
    entry_km: str
    ipa_km: Optional[str] = None
    definition_km: str
    definitions_list: List[str] = Field(default_factory=list)
    source: Optional[str] = "វចនានុក្រមជួន ណាត (ចេញផ្សាយគ្រឹះសករាជ ១៩៦៧)"
    pos: Optional[Union[str, List[str]]] = "ន."
    pos_full: Optional[str] = "នាម"


class EducationalCard(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    title_km: str
    register_label_km: str
    historical_context_km: str
    is_chuon_nath_official: bool


class CompoundTermSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    word: str
    pos: str
    definition: str


class MilitaryContextSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    title: str
    explanation: str
    breakdown: List[str]
    source: str


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    query: str
    grapheme_count: int
    status: str  # "exact_match", "phonetic_bridge_match", "composite_match", "loanword_match", "unmatched_queued", "success", "undefined", "error"
    is_official_chuon_nath: bool
    total: int
    resolved_variant: Optional[str] = None
    educational_card: EducationalCard
    linguistic_analysis: Dict[str, Any] = Field(default_factory=dict)
    linguistic_context: Dict[str, Any] = Field(default_factory=dict)
    results: List[SearchResultItem] = Field(default_factory=list)
    compound_terms: List[CompoundTermSchema] = Field(default_factory=list)
    compound_entries: List[SearchResultItem] = Field(default_factory=list)
    categorized_compounds: Dict[str, List[SearchResultItem]] = Field(default_factory=dict)
    military_reference: Optional[MilitaryContextSchema] = None
    predictive_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    composite_analysis: Optional[Dict[str, Any]] = None

