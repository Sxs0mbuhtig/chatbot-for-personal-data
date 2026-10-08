import logging
import sqlite3
import os
import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException

from schemas.search import SearchResponse, EducationalCard
from services.linguistic_engine import parse_khmer_linguistics, enrich_linguistic_context
from services.expressive_engine import expressive_engine
from services.predictive_engine import predictive_engine
from services.composite_etymology_engine import composite_etymology_engine
from services.batch_evaluator import batch_evaluator
from services.pos_mapper import resolve_pos_label
from services.lexicon_aggregator import aggregate_entry_results

# Safe imports for dependent entry and hierarchy tree helpers
try:
    from services.pos_mapper import resolve_dependent_entry
except ImportError:
    def resolve_dependent_entry(term: str) -> Optional[Dict[str, Any]]:
        return None

try:
    from services.lexicon_aggregator import get_lead_noun_context
except ImportError:
    def get_lead_noun_context(term: str) -> Optional[Dict[str, Any]]:
        return None

try:
    from khmer_normalizer import clean_khmer_text as normalize_khmer
except ImportError:
    def normalize_khmer(text: str) -> str:
        return text

try:
    from khmer_normalizer import sanitize_khmer_punctuation
except ImportError:
    def sanitize_khmer_punctuation(text: str) -> str:
        return text

# Optional Typesense Client Import with Failover Handling
try:
    import typesense
    typesense_client = typesense.Client({
        'nodes': [{
            'host': os.getenv('TYPESENSE_HOST', 'khmer_dict_typesense'),
            'port': os.getenv('TYPESENSE_PORT', '8108'),
            'protocol': os.getenv('TYPESENSE_PROTOCOL', 'http')
        }],
        'api_key': os.getenv('TYPESENSE_API_KEY', 'xyz'),
        'connection_timeout_seconds': 2
    })
except Exception:
    typesense_client = None

logger = logging.getLogger("km_lexicon.routers.search")
router = APIRouter(tags=["Search Engine"])

DB_PATH = "chuon_nath_fts.db"
LOG_FILE = "missing_lexicon_audit.log"
KHMER_NUMERALS = ["១", "២", "៣", "៤", "៥", "៦", "៧", "៨", "៩", "១០"]

POS_ORDER_MAP = {
    "ន.": 1,
    "កិ.": 2,
    "គុ.": 3,
    "គុ.ស.": 4,
    "កិ.គុ.": 5,
    "អ.ស.": 6,
    "និ.": 7
}


def log_undefined_term(term: str):
    """Logs unregistered search terms purely for future lexicon expansion."""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] UNREGISTERED_ENTRY: '{term}'\n"
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Failed to log undefined term '{term}': {e}")


def generate_jsonld_defined_term(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Schema.org DefinedTerm JSON-LD microdata for AEO."""
    return {
        "@context": "https://schema.org",
        "@type": "DefinedTerm",
        "name": doc.get("headword") or doc.get("entry_km", ""),
        "description": doc.get("definition") or doc.get("definition_km", ""),
        "phoneticText": doc.get("phonetic_ipa") or doc.get("ipa_km", ""),
        "inDefinedTermSet": doc.get("source") or "វចនានុក្រមជួន ណាត (ចេញផ្សាយគ្រឹះសករាជ ១៩៦៧)"
    }


def build_educational_card(
    query_str: str,
    ling_ctx: Dict[str, Any],
    is_official: bool = True,
    resolved_variant: Optional[str] = None
) -> EducationalCard:
    """Constructs EducationalCard instance based on query and linguistic context."""
    boundary = ling_ctx.get("boundary_note_km", "")
    hist_ctx = ling_ctx.get("educational_explanation_km", "")
    
    if resolved_variant:
        title = f"ព័ត៌មានអក្ខរាវិរុទ្ធ៖ {query_str} ➔ {resolved_variant}"
        hist_ctx = f"ពាក្យស្វែងរក «{query_str}» ត្រូវបានភ្ជាប់តាមសូរសំឡេងទៅទម្រង់ដើម «{resolved_variant}» (វចនានុក្រមជួនណាត)។ " + (hist_ctx or "")
        reg_label = "អក្ខរាវិរុទ្ធផ្លូវការ (វចនានុក្រមជួនណាត)" if is_official else "អក្ខរាវិរុទ្ធសម្រួល"
    else:
        title = "កំណត់ចំណាំអក្ខរាវិរុទ្ធ"
        reg_label = boundary or ("អក្ខរាវិរុទ្ធផ្លូវការ" if is_official else "ពាក្យមិនទាន់កត់ត្រា")

    if not is_official and ling_ctx.get("register") == "franco_khmer_loanword":
        reg_label = "ពាក្យកម្ចីបារាំង (French Loanword)"

    return EducationalCard(
        title_km=title,
        register_label_km=reg_label,
        historical_context_km=hist_ctx or "ជាអក្ខរាវិរុទ្ធផ្លូវការ មានសេចក្តីពន្យល់តាម វចនានុក្រមជួន ណាត ចេញគ្រឹះសករាជឆ្នាំ ១៩៦៧",
        is_chuon_nath_official=is_official
    )


def format_numbered_definitions(def_text: str) -> List[str]:
    """Splits multiple definition segments, sanitizes punctuation, and prefixes with Khmer numerals."""
    if not def_text:
        return []
    
    sanitized_def = sanitize_khmer_punctuation(def_text)
    raw_parts = [p.strip() for p in re.split(r'[;:]', sanitized_def) if p.strip()]
    numbered = []
    if len(raw_parts) <= 1:
        numbered.append(sanitized_def.strip())
    else:
        for idx, part in enumerate(raw_parts):
            num_str = KHMER_NUMERALS[idx] if idx < len(KHMER_NUMERALS) else str(idx + 1)
            sanitized_part = sanitize_khmer_punctuation(part)
            numbered.append(f"{num_str}. {sanitized_part}")
            
    return numbered


def consolidate_headword_entries(raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolidates multiple flat headword records with identical entry_km into ONE single record.
    Merges POS labels into an ordered list and definitions into a numbered definitions_list.
    """
    if not raw_results:
        return []

    grouped: Dict[str, Dict[str, Any]] = {}
    for r in raw_results:
        headword = r["entry_km"]
        if headword not in grouped:
            grouped[headword] = {
                "id": r["id"],
                "entry_km": headword,
                "ipa_km": r["ipa_km"],
                "source": r["source"],
                "pos_set": set(),
                "definitions_raw": [],
                "pos_full": r["pos_full"]
            }

        pos_val = r["pos"]
        if isinstance(pos_val, list):
            for p in pos_val:
                grouped[headword]["pos_set"].add(p)
        elif pos_val:
            grouped[headword]["pos_set"].add(pos_val)

        defs_list = r.get("definitions_list", [r["definition_km"]])
        for d in defs_list:
            if d not in grouped[headword]["definitions_raw"]:
                grouped[headword]["definitions_raw"].append(d)

    consolidated = []
    for hw, data in grouped.items():
        sorted_pos = sorted(list(data["pos_set"]), key=lambda p: POS_ORDER_MAP.get(p, 99))
        
        numbered_defs = []
        for idx, d in enumerate(data["definitions_raw"]):
            clean_d = re.sub(r"^[១២៣៤៥៦៧៨៩១០1-9]+\.\s*", "", d).strip()
            num_str = KHMER_NUMERALS[idx] if idx < len(KHMER_NUMERALS) else str(idx + 1)
            
            pos_prefix = f"({sorted_pos[0]}) " if sorted_pos else ""
            if not clean_d.startswith("("):
                numbered_defs.append(f"{num_str}. {pos_prefix}{clean_d}")
            else:
                numbered_defs.append(f"{num_str}. {clean_d}")

        primary_def = numbered_defs[0] if numbered_defs else ""
        consolidated.append({
            "id": data["id"],
            "entry_km": hw,
            "ipa_km": data["ipa_km"],
            "definition_km": primary_def,
            "definitions_list": numbered_defs,
            "source": data["source"],
            "pos": sorted_pos if len(sorted_pos) > 1 else (sorted_pos[0] if sorted_pos else "ន."),
            "pos_full": data["pos_full"]
        })

    return consolidated


def query_typesense(term: str, pos_filter: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Queries Typesense collection for dual-language and exact headword matches."""
    if not typesense_client:
        return []

    try:
        search_parameters = {
            'q': term,
            'query_by': 'canonical_headword,all_definitions_km,all_definitions_en',
            'sort_by': '_text_match:desc',
            'per_page': limit
        }

        if pos_filter:
            search_parameters['filter_by'] = f'pos_en_list:=[{pos_filter}]'

        res = typesense_client.collections['km_lexicon_entries'].documents.search(search_parameters)
        hits = []
        
        for hit in res.get('hits', []):
            doc = hit['document']
            homonyms = []
            if 'homonyms_json' in doc:
                try:
                    parsed = json.loads(doc['homonyms_json'])
                    homonyms = parsed.get("homonyms", [])
                except Exception:
                    pass

            hits.append({
                "id": doc.get("id", f"ts_{doc.get('canonical_headword')}"),
                "entry_km": doc.get("canonical_headword", term),
                "ipa_km": doc.get("phonetic_ipa", f"/{term}/"),
                "definition_km": doc.get("all_definitions_km", ""),
                "definitions_list": [doc.get("all_definitions_km", "")],
                "definition_en": doc.get("all_definitions_en", ""),
                "source": "AEO Enterprise Lexicon Engine",
                "pos": doc.get("pos_km_list", ["ន."]),
                "pos_full": ", ".join(doc.get("pos_en_list", ["noun"])),
                "homonyms": homonyms
            })
        return hits
    except Exception as e:
        logger.warning(f"Typesense search offline/error: {e}")
        return []


def query_sqlite_exact(term: str) -> Dict[str, Any]:
    """Queries SQLite DB for exact headword or normalized headword matches and consolidates senses."""
    if not os.path.exists(DB_PATH):
        logger.warning(f"Database file '{DB_PATH}' not found.")
        return {"exact_matches": []}
    
    norm_term = normalize_khmer(term)
    conn = None
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT id, headword, definition, pos 
            FROM dictionary 
            WHERE (norm_headword = ? OR headword = ?)
              AND TRIM(REPLACE(definition, '។', '')) != ''
            LIMIT 25
            """, 
            (norm_term, term)
        )
        exact_rows = cursor.fetchall()
        
        results = []
        seen_keys = set()

        for r in exact_rows:
            def_text = r[2].strip() if r[2] else ""
            cleaned_def = re.sub(r"^[\s\u17d4\u200b\u00a0]+|[\s\u17d4\u200b\u00a0]+$", "", def_text)
            if not cleaned_def:
                continue

            sanitized_def = sanitize_khmer_punctuation(cleaned_def)
            dedup_key = (r[1], sanitized_def)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            pos_label = resolve_pos_label(r[3])
            formatted_defs = format_numbered_definitions(sanitized_def)
            headword_ling = parse_khmer_linguistics(r[1], sanitized_def, is_official=True)
            ipa_val = headword_ling.get("phonetics", {}).get("primary_ipa", f"/{r[1]}/")

            results.append({
                "id": str(r[0]),
                "entry_km": r[1],
                "ipa_km": ipa_val,
                "definition_km": sanitized_def,
                "definitions_list": formatted_defs,
                "source": "វចនានុក្រមជួន ណាត (ចេញផ្សាយគ្រឹះសករាជ ១៩៦៧)", 
                "pos": pos_label,
                "pos_full": r[3] or "នាម"
            })
        
        consolidated_results = consolidate_headword_entries(results)
        return {"exact_matches": consolidated_results}
        
    except Exception as e:
        logger.error(f"Database lookup error for term '{term}': {e}")
        return {"exact_matches": []}
    finally:
        if conn:
            conn.close()


def query_compound_terms(prefix_term: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieves compound words starting with target prefix."""
    if not os.path.exists(DB_PATH) or len(prefix_term) < 1:
        return []

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        cursor = conn.cursor()
        
        query_pattern = f"{prefix_term}%"
        cursor.execute(
            """
            SELECT id, headword, definition, pos 
            FROM dictionary 
            WHERE (headword LIKE ? OR norm_headword LIKE ?)
              AND headword != ?
              AND norm_headword != ?
              AND TRIM(REPLACE(definition, '។', '')) != ''
            ORDER BY headword ASC, LENGTH(headword) ASC
            LIMIT ?
            """,
            (query_pattern, query_pattern, prefix_term, prefix_term, limit)
        )
        rows = cursor.fetchall()

        compounds = []
        seen_keys = set()
        for r in rows:
            clean_def = re.sub(r"^[\s\u17d4\u200b\u00a0]+|[\s\u17d4\u200b\u00a0]+$", "", r[2] or "")
            sanitized_def = sanitize_khmer_punctuation(clean_def)
            dedup_key = (r[1], sanitized_def)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            pos_label = resolve_pos_label(r[3])
            compounds.append({
                "word": r[1],
                "pos": pos_label,
                "definition": sanitized_def
            })
            
        return compounds
    except Exception as e:
        logger.error(f"Error querying compound terms for '{prefix_term}': {e}")
        return []
    finally:
        if conn:
            conn.close()


def resolve_bound_descriptors(term: str, exact_matches: list) -> Optional[Dict[str, Any]]:
    """Detects bound descriptors and attaches primary lead noun context."""
    bound_relations = {
        "កង": {
            "lead_noun": "នំ",
            "full_term": "នំកង",
            "description": "ប្រភេទនំប្រពៃណីខ្មែរធ្វើពីម្សៅដំណើប លញ់ជារាងកង បំពងខ្លាញ់ ជ្រលក់ទឹកស្ករត្នោតរំងាស់ និងរ៉ាយល្ងសពីលើ"
        }
    }
    return bound_relations.get(term)


@router.get("/search", response_model=SearchResponse)
async def search_lexicon(
    q: str = Query(..., description="Khmer query term or phrase"),
    pos: Optional[str] = Query(None