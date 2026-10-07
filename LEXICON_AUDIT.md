# Comprehensive Lexicon Audit Report (`LEXICON_AUDIT.md`)
**Project:** `km_lexicon` — Advanced Khmer Language Digester & Intelligence Engine  
**Audit Date:** September 21, 2026  
**Status:** Audit & Recommendations Complete (Conservative Evaluation Mode)

---

## 1. Executive Summary & Diagnostic Findings

An architectural audit of the `km_lexicon` codebase was conducted, covering Unicode normalization invariants, phonetic bridging, expressive digestion, 3-tier fallback query resolution, telemetry queueing, and Typesense indexing schemas.

### Key Key System Diagnostics & Strengths:
1. **Strict Canonical Normalization (`khmer_normalizer.py`)**: NFC normalization and Zero-Width Space (`U+200B`), NBSP (`U+00A0`), Soft Hyphen (`U+00AD`) stripping are properly enforced. Syllable reordering correctly places Consonant Shifters (`\u17c9`, `\u17ca`) after base consonants and before Coeng (`\u17d2`) foot subscripts.
2. **Robust Multi-Register Categorization (`services/expressive_engine.py`)**: `KhmerExpressiveEngine` classifies input queries across 6 registers (`expressive_onomatopoeia`, `franco_khmer_loanword`, `km_english_fusion`, `formal_classical`, `phonetic_modern`, and `colloquial_general`) and enriches results with Khmer-language educational context (`LinguisticContext`).
3. **Pydantic Boundary Integrity (`services/batch_evaluator.py` & `services/expressive_engine.py`)**: Telemetry records and digestion results are governed by schema models (`TelemetryPayload`, `UnmatchedQueryRecord`, `KhmerLinguisticEntry`, `ExpressiveDigestionResult`).

---

## 2. Technical Audit & Edge Case Analysis

### 2.1 Normalization & Phonetic Bridge (`khmer_normalizer.py`)
* **Independent Vowel Rules**: The mapping dictionary `INDEPENDENT_VOWEL_MAP` bridges key classical $\leftrightarrow$ modern pairs (`ឮ` $\leftrightarrow$ `លឺ`, `រឭក` $\leftrightarrow$ `រលឹក`/`រំលឹក`, `ឫស` $\leftrightarrow$ `រឹស`). However, substring replacement (`clean.replace(src, tgt)`) lacks word-boundary context, which risks unexpected partial replacements inside longer compound words if not constrained to grapheme boundaries.
* **Echo Compound Decomposition (`extract_echo_roots`)**: Handles even-length 4+ character reduplicated terms (`ងីងើ` $\rightarrow$ `['ងី', 'ងើ', 'ងីងើ']`) and strips trailing `ៗ` (`U+17D7` Lek To).
  * **Gap / Edge Case**: Odd-length or asymmetric echo compounds (e.g. 3-syllable or 5-syllable rhythmic expressives like `តតត` or `កិកិកិកិ`) default to single element list return `[root_text]` without full syllabic breakdown.
* **Grapheme Counting (`count_khmer_graphemes`)**: Correctly counts `U+17D7` (`លេខទោ` / `ៗ`) as an independent visual grapheme token alongside Khmer consonant-vowel clusters.

### 2.2 Expressive Engine & Register Classifier (`services/expressive_engine.py`)
* **Fuzzy Phonetic Generators**: `generate_phonetic_variants()` handles $L/R/ឡ$ swaps (`{ល, រ, ឡ}`), $K/Kh$ swaps, consonant shifters (`៉` $\leftrightarrow$ `៊`), and independent vowels.
* **Register Categorization**:
  * `franco_khmer_loanword` (e.g., `ស៊ីញ៉េ`, `កូដ`)
  * `km_english_fusion` (e.g., `ហ្វ្លូ`, `ប្រូ`)
  * `formal_classical` (Chuon Nath standard)
  * `phonetic_modern` (Keng Vannsak reform)
  * `expressive_onomatopoeia` (reduplicated terms & `ៗ`)
* **Deprecation Notice Warnings**: Pydantic models in `expressive_engine.py` and `batch_evaluator.py` use field name `register`, which triggers Python/Pydantic `UserWarning: Field name "register" in "LinguisticContext" shadows an attribute in parent "BaseModel"`.

### 2.3 Search Query Resolution & Telemetry (`routers/search.py`)
* **Fallback Resolution Execution**:
  * `routers/search.py` currently relies strictly on local SQLite lookup (`query_sqlite_exact()`) or falls back to an `unlisted_1` payload.
  * **Gap**: `routers/search.py` currently imports `parse_khmer_linguistics` from `services.linguistic_engine` and doesn't invoke `expressive_engine.digest_input()` or query Typesense/vector search.
  * **Status Mapping Alignment**: Test `test_search_resolution_loanwords_and_expressives` in `tests/test_expressive_engine.py` expects status responses such as `loanword_match`, `exact_match`, or `phonetic_bridge_match`, whereas `routers/search.py` returns `"status": "success"` or `"status": "undefined"`.
* **Telemetry Logging**: Unmatched terms are logged via file append (`log_undefined_term`), but require integration with `batch_evaluator.queue_unmatched_query` for Pydantic-validated JSON/JSONL queueing.

### 2.4 Analysis of Query Expansion Amplification in Typesense
* **Index Amplification Risk**: When `build_typesense_payload()` is invoked, `generate_phonetic_variants()` generates full cartesian permutations of $L/R/\text{ឡ}$ alternations, shifters, and independent vowels. For a word with multiple $L/R$ consonants and shifters, variant generation can create dozens of strings per document.
* **Recommendation**: Cap `phonetic_variants` set size (e.g., top 10 most probable phonetic variants) or index variants strictly into an `infix: false` array field (`variants`) to avoid index bloat and search relevance noise in Typesense.

---

## 3. Recommended Conservative Code Patches

### Patch 1: `khmer_normalizer.py` (Safe Independent Vowel Substitution & Echo Roots)
```python
# Proposed refinement for extract_echo_roots to support syllabic splitting
def extract_echo_roots(text: str) -> list[str]:
    if not text:
        return []
    clean = clean_khmer_text(text)
    root_text = re.sub(r"[\s\u17d7]+$", "", clean).strip()
    
    n = len(root_text)
    if n >= 4 and n % 2 == 0:
        half = n // 2
        s1, s2 = root_text[:half], root_text[half:]
        if s1 and s2:
            return [s1, s2, root_text]
            
    return [root_text]
```

### Patch 2: `services/expressive_engine.py` (Pydantic Field Shadowing Fix)
```python
# Rename field or alias to prevent shadowing Pydantic internal attribute
class LinguisticContext(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    register: str = Field(..., alias="register", description="Linguistic register category")
```

### Patch 3: `routers/search.py` (Integrating Expressive Engine & Telemetry Queue)
```python
# Integrate expressive engine digestion & 3-tier fallback strategy
from services.expressive_engine import expressive_engine
from services.batch_evaluator import batch_evaluator

# Inside search_lexicon endpoint:
digestion = expressive_engine.digest_input(query_str)
if not is_official:
    batch_evaluator.queue_unmatched_query(
        raw_query=query_str,
        normalized_root=digestion.normalized_root,
        detected_register=digestion.register_analysis.primary_register
    )
```

---

## 4. Strategic Recommendations Roadmap

1. **Phase 1: Query Resolution Alignment (Immediate)**
   - Wire `expressive_engine.digest_input()` into `routers/search.py` to enable 3-tier resolution:
     - Tier 1: Direct Exact Match
     - Tier 2: Phonetic Bridge / Independent Vowel Variant Match
     - Tier 3: Echo Root Decomposition & Vector Semantic Fallback
   - Harmonize response status codes (`exact_match`, `phonetic_bridge_match`, `loanword_match`, `unmatched_queued`).

2. **Phase 2: Typesense Indexing Optimization**
   - Deduplicate and bound phonetic variant generation in `build_typesense_payload()` to max 10 variants per term to prevent query expansion amplification.

3. **Phase 3: Telemetry Batch Curation Automation**
   - Run periodic cron batch evaluations using `LLMBatchCurator` with rate-limited Gemini key rotation to auto-curate high-frequency unmatched search queries.
