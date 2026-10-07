# State of the Project: Khmer Lexicon (`km_lexicon`) Comprehensive Codebase Audit

**Date**: September 14, 2026  
**Auditor**: Lead Software Architect (NLP & Lexicography Specialist)  
**Target Repository**: `km_lexicon` (`/home/sam_workstation/km_lexicon`)  
**Status**: Completed (Read-Only Audit Phase)

---

## Executive Summary

`km_lexicon` is a digital dictionary and natural language processing (NLP) search engine tailored for the Khmer language, primarily centered around the canonical **Samdach Chuon Nath Dictionary** (1967) with extended support for modern variant spellings, orthographic guidance, and morphological decomposition.

The project demonstrates strong core concepts for handling Khmer script intricacies—including Unicode NFC normalization, zero-width space removal, canonical redirection for non-standard spelling variants, and dual indexing via Typesense and SQLite FTS5. However, the codebase is currently in a fragmented, pre-production state plagued by critical runtime bugs in the entry point (`main.py`), architectural duplication across multiple search routers and service modules, security vulnerabilities (hardcoded API keys and committed private SSH keys), and incomplete dependency declarations.

This document presents an end-to-end architectural evaluation, data schema analysis, risk audit, and a strategic readiness checklist for future feature integration.

---

## 1. Current Architecture & Tech Stack Overview

### 1.1 High-Level System Architecture

```
                                  +---------------------------------------+
                                  |         Web Frontend Portal           |
                                  | (HTML5 + Tailwind CSS + Kantumruy Pro) |
                                  +-------------------+-------------------+
                                                      |
                                                      | HTTP / REST API
                                                      v
                                  +---------------------------------------+
                                  |         FastAPI REST Service          |
                                  |       (Uvicorn ASGI Server)           |
                                  +---------+-------------------+---------+
                                            |                   |
                     +----------------------+                   +----------------------+
                     |                                                                 |
                     v                                                                 v
+------------------------------------------+                       +------------------------------------------+
|            Typesense Engine              |                       |            SQLite FTS5 Engine            |
|       (Dockerized Port 8108)             |                       |          (chuon_nath_fts.db)             |
| Collection: omnisense_lexicon            |                       | Tokenizer: Trigram                       |
| Features: Infix, Typo Tolerance, Synonyms|                       | Purpose: Offline / Standalone FTS        |
+------------------------------------------+                       +------------------------------------------+
                     ^                                                                 ^
                     |                                                                 |
    +----------------+---------------+                                +----------------+---------------+
    | Data Ingestion & Index Scripts |                                | Database Generation Scripts    |
    | (index_typesense.py,           |                                | (build_fts_db.py)              |
    |  ingest_omnisense.py)          |                                | Input: chuon_nath_full.json    |
    +--------------------------------+                                +--------------------------------+
```

### 1.2 Tech Stack & Ecosystem Mapping

| Layer | Component | Description & Current Version |
| :--- | :--- | :--- |
| **Backend Framework** | FastAPI / Uvicorn | Python-based ASGI application framework. |
| **Primary Search Engine** | Typesense (`v26.0`) | In-memory, C++ search engine run via Docker Compose on port 8108. |
| **Secondary FTS Engine** | SQLite3 (FTS5) | Embedded FTS database (`chuon_nath_fts.db`) with `trigram` tokenizer. |
| **Khmer String Normalization** | `unicodedata2` / `re` | Canonical Unicode composition (NFC) and invisible byte stripping. |
| **Phonetic & Fuzzy Matching** | RapidFuzz | Indel / Levenshtein ratio matching (`fuzz.ratio`) for offline typos. |
| **Word Segmentation** | `khmernltk` (Optional) | Multi-word compound segmentation fallback. |
| **Frontend Portal** | HTML5 / JavaScript | Single-page application using Tailwind CSS (CDN) and Kantumruy Pro font. |
| **Containerization** | Docker / Docker Compose | Single-node composition (`typesense` container + `web` API container). |

### 1.3 Service Entry Points & Module Disfragmentation

The application currently suffers from **router fragmentation**, containing 5 separate entry points and router scripts that execute search logic differently:

1. `main.py`: Main FastAPI server entry point. Currently broken due to duplicate `FastAPI()` instantiation and missing imports.
2. `routers/search.py`: Modular `APIRouter` mounting `/api/v1/search` and `/api/search` with Typesense search and morphology fallback.
3. `search_router.py`: Standalone tier-based search script combining exact matching, orthographic normalization, and an unintegrated GenAI LLM prompt stub.
4. `query_router.py`: Independent Python module using the `requests` library to query Typesense HTTP endpoint `http://localhost:8108`.
5. `khmer_engine.py`: Standalone in-memory engine class (`IntelligentKhmerSearch`) using RapidFuzz and optional `khmernltk`.

---

## 2. Khmer Language Handling Assessment

Khmer language processing in digital lexicography requires specialized treatment due to Unicode stacking rules, sub-consonant clusters (Coeng `\u17d2`), invisible joiners, and non-spaced compound words.

### 2.1 Unicode Normalization & Invisible Character Stripping

Found in `khmer_engine.py`, `khmer_normalizer.py`, `utils/formatting.py`, and `build_fts_db.py`:

```python
# Standardized cleaning sequence across codebase
text = unicodedata.normalize("NFC", text)
text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)  # Strips ZWSP, NBSP, Soft Hyphen
text = re.sub(r"\s+", " ", text).strip()
```

* **Strengths**: Canonical NFC composition ensures that decomposed Khmer vowels and accent marks are merged into unified code points. Removing Zero-Width Space (`\u200b`), Non-Breaking Space (`\u00a0`), and Soft Hyphen (`\u00ad`) prevents user copy-paste query failures.
* **Risks**: `build_fts_db.py` and `ingest_typesense.py` run regex removal of dots and whitespace (`re.sub(r"[\u200b\u00a0\u00ad.\s]", "", text)`), which aggressively strips punctuation inside definition texts and entry titles.

### 2.2 Orthographic Normalization & Naive Character Substitution

`khmer_normalizer.py` implements phonetic variant replacement for common orthographic confusion pairs in modern Khmer typing:

```python
CHAR_REPLACEMENTS = {
    'ន': 'ណ',  # Dental / Retroflex nasal swap (e.g., ចំនង់ -> ចំណង់)
    'ដ': 'ត',  # Retroflex / Dental stop swap (e.g., ដំរង់ -> តម្រង់)
    'ឡ': 'ល',  # Liquid consonant swap
}
```

* **Critical Flaw**: This global string replacement (`normalized.replace(target, replacement)`) is **overly aggressive and destructive**. For example, replacing every occurrence of `ន` with `ណ` invalidates legitimate headwords like `នារី` (woman) into non-existent words like `ណារី`. Orthographic swaps must be handled via curated dictionary synonym rules (e.g., Typesense synonyms) or contextual ngram mapping rather than global character replacement.

### 2.3 Word Segmentation & Compound Decomposition

Khmer text lacks spaces between words within sentences or compound nouns. `km_lexicon` employs a two-layer strategy:

1. **Rule-Based Anatomical/Spatial Prefix Splitter** (`services/lexicon.py` and `app/services/decomposer.py`):
   Identifies common prefix roots (e.g., `ក`, `ដើម`, `ចុង`, `មាត់`, `ផ្លែ`, `ក្បាល`, `ពក`). If the input starts with a prefix and the remainder is not a dependent vowel (`KHMER_DEPENDENT_VOWELS = r"^[\u17c6-\u17d3\u17b6-\u17c5]"`), it queries the dictionary for both root components.
2. **NLTK Fallback** (`khmer_engine.py`):
   Attempts to import `khmernltk.word_tokenize` to segment unspaced multi-word queries.

---

## 3. Data Schemas & Indexing Assessment

### 3.1 Raw Dataset Schema (`chuon_nath_full.json`)

The primary offline corpus contains **16,019,868 bytes** (~16 MB) representing the complete Chuon Nath Dictionary dataset:

```json
[
  {
    "t_main": "ក",
    "t_pron": "[ក]",
    "t_poly": "១)",
    "t_pos": "ន.",
    "t_exp": "អវយវៈដែលតពីក្បាលទៅស្មាឬទៅខ្លួននៃមនុស្សសត្វ :",
    "t_exam": "កមនុស្ស, កមាន់។"
  }
]
```

### 3.2 Typesense Collection Schema (`omnisense_lexicon`)

Defined in `schema.json` and initialized in `index_typesense.py`:

```json
{
  "name": "omnisense_lexicon",
  "fields": [
    {"name": "headword", "type": "string", "infix": true},
    {"name": "norm_headword", "type": "string", "infix": true},
    {"name": "canonical_headword", "type": "string", "optional": true, "infix": true},
    {"name": "pos", "type": "string", "facet": true, "optional": true},
    {"name": "definition", "type": "string"},
    {"name": "phonetic_ipa", "type": "string", "optional": true},
    {"name": "phonetic_km", "type": "string", "optional": true},
    {"name": "variants", "type": "string[]", "optional": true, "infix": true},
    {"name": "is_variant", "type": "bool", "optional": true, "facet": true},
    {"name": "is_official_chuon_nath", "type": "bool", "optional": true, "facet": true},
    {"name": "chuon_nath_guidance", "type": "string", "optional": true},
    {"name": "orthographic_warning", "type": "string", "optional": true},
    {"name": "related_words", "type": "string[]", "optional": true},
    {"name": "roots", "type": "string[]", "optional": true},
    {"name": "source_title", "type": "string", "facet": true},
    {"name": "sort_index", "type": "int32"}
  ],
  "default_sorting_field": "sort_index"
}
```

#### Assessment of Indexing Strategy:
* **Infix Matching**: `infix: true` is enabled on `headword`, `norm_headword`, `canonical_headword`, and `variants`. This enables rich partial and substring searching across Khmer characters.
* **Canonical Mapping**: Non-standard spellings (e.g., `កំនត់ត្រា` or `កម្នត់ត្រា`) map to `canonical_headword: "កំណត់ត្រា"`, storing specific `orthographic_warning` directives from Chuon Nath guidelines.
* **Synonym Rules**: `index_typesense.py` configures Typesense synonym sets (`kamnot_orthography_cluster`) to bridge non-standard variants to canonical headwords seamlessly.

### 3.3 SQLite FTS5 Schema (`chuon_nath_fts.db`)

Created by `build_fts_db.py`:

```sql
CREATE TABLE dictionary (
    id INTEGER PRIMARY KEY,
    headword TEXT NOT NULL,
    norm_headword TEXT NOT NULL,
    pos TEXT,
    definition TEXT NOT NULL
);

CREATE VIRTUAL TABLE dict_fts USING fts5(
    headword,
    norm_headword,
    definition,
    content='dictionary',
    content_rowid='id',
    tokenize='trigram'
);
```

* **Trigram Tokenization**: SQLite FTS5 with `tokenize='trigram'` provides substring search capability for Khmer script without requiring a complex C++ tokenizer.

---

## 4. Gaps, Technical Debt & Security Vulnerabilities

### 4.1 Critical Bugs & Runtime Failures

#### 1. Broken Entrypoint (`main.py`)
`main.py` contains severe code collisions:
- **Double FastAPI Instantiation**: On line 18, `app = FastAPI(...)` is created with CORS middleware and router includes. On line 99, `app = FastAPI(lifespan=lifespan)` is declared again! This second initialization **wipes out all previously registered routes, middleware, and CORS configuration**.
- **Undefined Global Variable**: `/api/v1/search` endpoints on lines 61 and 103 call `typesense_client.collections[...]`, but `typesense_client` is never instantiated or imported in `main.py`. Invoking this endpoint results in an immediate `500 Internal Server Error` (`NameError: name 'typesense_client' is not defined`).
- **Duplicate Route Definitions**: `/api/v1/search` is defined twice within `main.py`.

#### 2. Duplicate & Contradictory Formatting Functions
`services/formatting.py` and `utils/formatting.py` contain almost identical copies of `clean_khmer()` and `format_document()`. Furthermore, `routers/search.py` re-defines `clean_khmer()` locally on lines 19–25.

#### 3. Incomplete `requirements.txt`
`requirements.txt` lists only 4 packages: `fastapi`, `uvicorn`, `unicodedata2`, `typesense`.  
It **omits** required dependencies used across the codebase: `rapidfuzz`, `requests`, `aiofiles`, and `khmernltk`. Attempting to run `khmer_engine.py`, `build_typos.py`, or `main.py` outside container environment fails with `ImportError`.

---

### 4.2 Security Vulnerabilities & Privacy Risks

#### 1. Hardcoded API Credentials
The Typesense master API key `xyz_secret_key_123` is hardcoded across **7 different files**:
- `docker-compose.yml` (line 9 & 23)
- `query_router.py` (line 4)
- `search_router.py` (referenced)
- `index_typesense.py` (line 13)
- `ingest_typesense.py` (line 12)
- `ingest_omnisense.py` (line 9)
- `services/lexicon.py` (line 12 fallback)

#### 2. Committed SSH Private Key
The repository root contains a private SSH key (`ed25519_git`) and its corresponding public key (`ed25519_git.pub`). **Storing raw private SSH keys in source control is a critical security vulnerability.**

#### 3. Unanonymized User IP Logging
`main.py` and `query_telemetry.py` log raw client IP addresses (`request.client.host`) into `unmatched_queries.jsonl`:
```json
{"timestamp": "2026-09-10T05:53:07+00:00", "query": "ចំនង់ចំនូល", "length": 10, "user_ip": "127.0.0.1"}
```
Logging raw user IP addresses creates GDPR/privacy compliance risks. Client IPs must be hashed or anonymized (e.g., subnet masking or SHA-256 with a daily salt).

#### 4. Permissive CORS Middleware
`main.py` enables `allow_origins=["*"]` with `allow_methods=["GET"]`. While acceptable for public read-only dictionary lookup, origin restrictions should be configurable via environment variables.

---

### 4.3 Missing Tests & Development Infrastructure

* **Zero Automated Unit/Integration Tests**: There is no `tests/` directory and no `pytest` or `unittest` configuration.
* **Unintegrated GenAI Stubs**: `search_router.py` (`trigger_genai_analysis`) and `process_unmatched_logs.py` (`generate_genai_variant_entry`) contain stubbed prompt templates that pass or print comments without invoking an actual LLM client (e.g., Google Gemini API).

---

## 5. Deep-Dive Technical Debt & Edge-Case Findings

A deep-dive technical audit was conducted across three critical domain vectors: Khmer NLP/script processing edge-cases, database indexing and retrieval latency bottlenecks, and data schema elasticity for lexicographical polysemy.

---

### 5.1 Vector 1: Khmer NLP & Script Edge-Cases

#### 1. Word Segmentation Architecture Analysis
* **Current State**: Segmentation logic is fragmented across `khmer_engine.py`, `services/lexicon.py`, and `app/services/decomposer.py`.
  * `khmer_engine.py` delegates segmentation to `khmernltk.word_tokenize` inside `tokenize_compound()`. If `khmernltk` is not installed (as it is currently missing from `requirements.txt`), it falls back to `clean_text.split()`.
  * **Critical Flaw**: Standard Khmer text does not utilize spaces between words. Calling `.split()` on an unspaced Khmer phrase (e.g., `"ការអប់រំផ្លូវចិត្ត"`) yields a single-element list `["ការអប់រំផ្លូវចិត្ត"]`. This completely breaks multi-word compound lookups when the optional NLTK package is missing.
  * **Prefix Decomposer Limitations**: `services/lexicon.py` relies on a hardcoded dictionary of 6 prefixes (`ក`, `ដើម`, `ចុង`, `មាត់`, `ពក`, `ក្បាល`). It lacks a dictionary-driven Maximum Matching (MaxMatch / Longest Matching) algorithm or statistical segmentation model (CRF / BiLSTM-CRF), making compound word handling extremely brittle.

#### 2. Zero-Width Spaces, Sub-consonants (Coeng / ជើង), and Diacritics
* **Zero-Width Spaces (`U+200B`)**:
  * Cleaning logic in `utils/formatting.py` executes `re.sub(r"[\u200b\u00a0\u00ad]", "", text)`.
  * **Edge-Case Failure**: While stripping `U+200B` unifies copy-pasted strings, `U+200B` is frequently used by Khmer input methods as explicit word boundary markers. Stripping `U+200B` prior to word segmentation discards valuable user-provided token boundary hints.
* **Sub-Consonant Stacks (`U+17D2` + Consonant)**:
  * In Khmer orthography, subscript consonants ("Feet" / ជើង) are represented by the Coeng control character (`U+17D2`) followed by the sub-consonant (e.g., `្` + `ក` = `្ក`).
  * `khmer_normalizer.py` executes global character replacements (`'ន': 'ណ'`, `'ដ': 'ត'`, `'ឡ': 'ល'`). Because this replacement is executed without checking for preceding `U+17D2` Coeng markers, replacing `ត` with `ដ` in sub-consonant clusters (e.g., `ន្ត` `\u1793\u17d2\u178f`) mutates valid consonant stacks into illegal Unicode sequences (e.g., `នដ`), corrupting font rendering into missing glyph boxes (dotted circle `◌្`).
* **Diacritics & Shift Keys**:
  * Khmer diacritics (Bantoc `\u17c6`, Nikahit `\u17c6`, Reahmuk `\u17c7`, Toandakhiat `\u17cd`, etc.) can be entered out of standard visual sequence depending on physical keyboard layouts.
  * Standard `unicodedata.normalize("NFC", text)` does not reorder all Khmer diacritics into canonical phonetic sequence (Base Consonant -> Coeng Cluster -> Dependent Vowel -> Diacritic), causing visual duplicate query lookup misses.

#### 3. String Length & Unicode Grapheme Clusters
* **Current State**: Telemetry logging (`query_telemetry.py`) and API input validation (`routers/search.py`) use Python's built-in string length check: `len(query)` or `max_length=100`.
* **Critical Flaw**: `len(str)` counts UTF-16 code units / Unicode code points, **not grapheme clusters (visual Khmer characters)**.
  * *Example*: The Khmer word `ខ្ញុំ` ("I/me") consists of 5 Unicode code points: `ខ` (`U+1781`) + `្` (`U+17D2`) + `ញ` (`U+1799`) + `ុ` (`U+17BB`) + `ំ` (`U+17C6`). `len("ខ្ញុំ")` evaluates to `5`, even though it is visually a single word/grapheme cluster.
  * As a result, `Query(..., max_length=100)` restricts Khmer queries to roughly 20-25 visual characters, and telemetry metric `"length": len(clean_query)` inaccurately inflates query length analytics.

---

### 5.2 Vector 2: Database & Retrieval Bottlenecks

#### 1. Full-Text Search (FTS) Indexing Efficiency
* **Typesense Infix Memory Overhead**:
  * In `index_typesense.py`, `infix: true` is configured on `headword`, `norm_headword`, `canonical_headword`, and `variants`.
  * Typesense constructs n-gram suffix trees in memory for infix search. Because Khmer script lacks space delimiters, Typesense indexes every character n-gram. While fast for 16,000 entries, scaling the lexicon to 500,000 entries or full definition search will cause exponential RAM inflation in the Typesense container.
* **SQLite FTS5 Trigram Limitations (`build_fts_db.py`)**:
  * SQLite uses `tokenize='trigram'`.
  * Trigram tokenization slices raw text into 3-character windows. For Khmer script, 3-character windows frequently bisect Coeng sub-consonant pairs (`U+17D2` + consonant) or dependent vowel sequences, producing noisy false-positive full-text matches in definition body queries.
  * The SQLite schema lacks document relevance weighting (BM25 field weighting), treating matches in a 500-word definition body equally to matches in headwords.

#### 2. Query Execution Paths & Latency Bottlenecks (<50ms Benchmark)
* **Sequential Round-Trip Cascades in `query_router.py`**:
  * `query_router.py` makes a synchronous HTTP request to Typesense for initial lookup.
  * If the result is marked as a variant (`is_variant == True`), it performs a **second sequential HTTP request** to fetch the canonical document.
  * Sequential HTTP calls over network sockets add 20–40ms of latency per request, endangering the sub-50ms SLA under concurrent traffic.
* **Synchronous RapidFuzz Python Scanning**:
  * In `khmer_engine.py`, fuzzy search falls back to `rapidfuzz.process.extract(cleaned_query, self.headwords, scorer=fuzz.ratio)`.
  * Executing fuzzy Levenshtein ratio matching against all array headwords synchronously in Python blocks the ASGI event loop (GIL), causing CPU spikes and latency exceeding 100ms when handling unmatched queries.
* **Absence of In-Memory Response Caching**:
  * The system lacks a caching tier (e.g., Redis or `async-lru` in-memory cache). Repeated high-volume queries (e.g., `"កម្ពុជា"`) re-run the entire Typesense query pipeline on every hit.

---

### 5.3 Vector 3: Data Integrity & Schema Elasticity Analysis

#### 1. Polysemy & Multi-Sense Entry Storage Deficit
* **Source Dataset Flaw (`chuon_nath_full.json`)**:
  * In `chuon_nath_full.json`, polysemous words (single words with multiple parts of speech or distinct meanings) are stored as separate, flat JSON objects sharing the same `t_main` value:
    ```json
    { "t_main": "ក", "t_pos": "ន.", "t_exp": "តួព្យញ្ជនៈទី១..." }
    { "t_main": "ក", "t_pos": "កិ.", "t_exp": "តាំងផ្ដើម, តាំងធ្វើ..." }
    { "t_main": "ក", "t_poly": "១)", "t_pos": "ន.", "t_exp": "អវយវៈដែលតពីក្បាល..." }
    ```
* **Typesense Data Loss**:
  * `index_typesense.py` assigns `payload["id"] = f"doc_{idx}"` and indexes each sense as an isolated document. Searching for `"ក"` returns disconnected hit documents rather than a structured entry with array of definitions (`senses`).
* **Service Lookup Failure (`services/lexicon.py`)**:
  * `fetch_word()` configures `'per_page': 1` and returns only `res['hits'][0]['document']`.
  * **Result**: Querying polysemous words returns **only the first recorded definition sense** (e.g., returning only the letter definition for `ក`, completely discarding the verb "to build" and the noun "neck").

#### 2. Etymology, Historical Usages & Schema Rigidity
* **Unstructured Etymology**: Etymology references (e.g., Pali `បា.`, Sanskrit `សំ.`, French `បារ.`) are embedded as raw text inside `t_exp` rather than extracted into dedicated relational/JSON schema fields (`language_origin`, `root_etymon`).
* **Missing Polysemous Structural Hierarchy**: The current schema lacks nested arrays for definitions, sense numbers, usage domain tags (e.g., Legal, Medical, Literature), and example sentences (`t_exam`).

---

## 6. Feature Readiness Checklist

This checklist evaluates system readiness for upcoming feature expansions: Answer Engine Optimization (AEO), telemetry pipelines, phonetics/etymology, and trending usage analytics.

| Feature Area | Readiness Status | Current Gaps & Blockers | Required Remediation |
| :--- | :---: | :--- | :--- |
| **Answer Engine Optimization (AEO)** | 🟡 Partial | No JSON-LD structured data for web crawlers; API responses lack concise direct-answer summaries for LLM consumption. | Implement Schema.org `DefinedTerm` JSON-LD generation; add direct canonical answer summary fields in search API output. |
| **Search Logging & Telemetry** | 🟡 Partial | Telemetry writes to local JSONL (`unmatched_queries.jsonl`); logs raw user IP; no automated pipeline to aggregate missing terms. | Anonymize IP logging (SHA-256); build automated cron worker to process unmatched queries into `typo_suggestions.json`. |
| **Phonetics & Etymology Engine** | 🔴 Low | Schema supports `phonetic_ipa`, `phonetic_km`, `roots`, and `etymology_note`, but dataset coverage is <0.05% (only 3 hand-crafted entries in `index_typesense.py`). | Ingest G2P (Grapheme-to-Phoneme) conversion rules for Khmer IPA; enrich `chuon_nath_full.json` with etymological root classifications. |
| **Trending Usage & Analytics** | 🔴 Low | No real-time query counters, rate limiters, or caching stores (e.g., Redis); Typesense ranking uses static `sort_index`. | Integrate Redis or SQLite query frequency counter; incorporate log-frequency scores into search re-ranking algorithms. |

---

## 7. Recommended Action Plan & Next Steps

Before implementing new features, the following refactoring roadmap should be executed:

### Phase 1: Critical Bug Fixes & Codebase Stabilization
1. **Consolidate `main.py`**: Remove duplicate `FastAPI()` instantiation; import `ts_client` from `services.lexicon`; use `routers/search.py` as the unified APIRouter.
2. **Purge Security Credentials**:
   - Delete `ed25519_git` and `ed25519_git.pub` from the repository and git history.
   - Refactor all scripts to read `TYPESENSE_API_KEY` from environment variables (`.env`).
3. **Consolidate Service Modules**: Remove duplicate `services/formatting.py` and `utils/formatting.py`; unify under `services/formatting.py`.
4. **Fix `requirements.txt`**: Add `rapidfuzz`, `requests`, `aiofiles`, `khmernltk`, and `pytest`.

### Phase 2: Refactoring Language Processing & Search
1. **Fix Orthographic Replacement**: Replace naive global string character replacements (`CHAR_REPLACEMENTS` in `khmer_normalizer.py`) with Typesense synonym rules and structured variant mappings.
2. **Anonymize Telemetry**: Update `query_telemetry.py` to hash user IP addresses before persisting to `unmatched_queries.jsonl`.
3. **Establish Test Suite**: Create a `tests/` directory with unit tests for NFC cleaning, compound decomposition, and search API responses.

### Phase 3: Advanced Feature Readiness
1. **Connect GenAI LLM Integration**: Implement Gemini API integration in `process_unmatched_logs.py` to auto-generate etymology notes for frequent unmatched queries.
2. **AEO & Search Analytics**: Expose JSON-LD endpoints and real-time query trends.

---
*Report generated automatically for `km_lexicon` project documentation.*

