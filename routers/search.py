import logging
import sqlite3
import os
import re
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

logger = logging.getLogger("km_lexicon.routers.search")
router = APIRouter(tags=["Search Engine"])

DB_PATH = "chuon_nath_fts.db"
LOG_FILE = "missing_lexicon_audit.log"
KHMER_NUMERALS = ["១", "២", "៣", "៤", "៥", "៦", "៧", "៨", "៩", "១០"]


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


from khmer_normalizer import sanitize_khmer_punctuation

POS_ORDER_MAP = {
    "ន.": 1,
    "កិ.": 2,
    "គុ.": 3,
    "គុ.ស.": 4,
    "កិ.គុ.": 5,
    "អ.ស.": 6,
    "និ.": 7
}

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
        # Sort POS tags according to POS_ORDER_MAP
        sorted_pos = sorted(list(data["pos_set"]), key=lambda p: POS_ORDER_MAP.get(p, 99))
        
        # Build numbered definitions list: ១. (គុ.) ..., ២. (កិ.) ...
        numbered_defs = []
        for idx, d in enumerate(data["definitions_raw"]):
            # Strip pre-existing numeral prefixes if any to re-number cleanly
            clean_d = re.sub(r"^[១២៣៤៥៦៧៨៩១០1-9]+\.\s*", "", d).strip()
            num_str = KHMER_NUMERALS[idx] if idx < len(KHMER_NUMERALS) else str(idx + 1)
            
            # Extract POS prefix if available
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
        
        # Consolidate duplicate headwords into a single record with merged definitions_list
        consolidated_results = consolidate_headword_entries(results)
            
        return {"exact_matches": consolidated_results}
        
    except Exception as e:
        logger.error(f"Database lookup error for term '{term}': {e}")
        return {"exact_matches": []}
    finally:
        if conn:
            conn.close()


def query_compound_terms(prefix_term: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Retrieves compound words starting with target prefix (e.g., កង% -> កងទ័ព, កងពល), excluding direct exact matches."""
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
    """
    Detects if a search term acts as a bound descriptor (e.g., 'កង' in 'នំកង')
    and attaches the primary Lead Noun relationship.
    """
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
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    query_str = q.strip()
    if not query_str:
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")

    try:
        # 1. Expressive Engine Digestion & 4-Tier Search Resolution Strategy
        digestion = expressive_engine.digest_input(query_str)
        status_code = "unmatched_queued"
        db_results = []
        is_official = False
        resolved_variant = None

        # --- Tier 1: Direct Normalized Root Match ---
        t1_data = query_sqlite_exact(query_str)
        if t1_data["exact_matches"]:
            db_results = t1_data["exact_matches"]
            is_official = True
            comp_analysis = composite_etymology_engine.analyze_term(query_str)
            if comp_analysis.etymology.etymology_class != "native_km" or digestion.register_analysis.primary_register in ("franco_khmer_loanword", "km_english_fusion"):
                status_code = "loanword_match"
            else:
                status_code = "exact_match"

        # --- Tier 2: Phonetic Bridge & Independent Vowel Match ---
        if not is_official and digestion.phonetic_variants:
            for variant in digestion.phonetic_variants:
                if variant == query_str:
                    continue
                t2_data = query_sqlite_exact(variant)
                if t2_data["exact_matches"]:
                    db_results = t2_data["exact_matches"]
                    is_official = True
                    resolved_variant = variant
                    status_code = "phonetic_bridge_match"
                    break

        # --- Tier 3: Composite Word Component Breakdown & Echo Decomposition Match ---
        composite_res = composite_etymology_engine.analyze_term(query_str)
        matched_components = []
        if not is_official:
            if composite_res.etymology.etymology_class in ("french", "english", "pali_sanskrit", "thai", "vietnamese", "chinese") or digestion.register_analysis.primary_register in ("franco_khmer_loanword", "km_english_fusion"):
                status_code = "loanword_match"
            elif composite_res.is_composite:
                for comp in composite_res.components:
                    if comp.is_in_dictionary and comp.definition:
                        matched_components.append({
                            "id": f"comp_{comp.component}",
                            "entry_km": comp.component,
                            "ipa_km": f"/{comp.component}/",
                            "definition_km": comp.definition,
                            "definitions_list": format_numbered_definitions(comp.definition),
                            "source": "សមាសភាគពាក្យ (Composite Morpheme)",
                            "pos": "សមាសភាគ",
                            "pos_full": "សមាសភាគពាក្យ"
                        })
            if matched_components:
                db_results = matched_components
                is_official = False
                status_code = "composite_match"

        # --- Tier 4: Zero-hit Capture -> Generate Predictive Suggestions + Queue Unmatched Entry ---
        predictive_candidates = []
        if not is_official and status_code == "unmatched_queued":
            # Queue unmatched query to telemetry queue
            batch_evaluator.queue_unmatched_query(
                raw_query=query_str,
                normalized_root=digestion.normalized_root,
                detected_register=digestion.register_analysis.primary_register
            )
            log_undefined_term(query_str)

            # Generate top 10 predictive suggestions
            suggestions = predictive_engine.generate_suggestions(query_str, max_candidates=10)
            predictive_candidates = [s.model_dump() for s in suggestions]

        # 2. Fetch Compound Terms & Domain Knowledge
        compounds = query_compound_terms(query_str, limit=15)
        aggregated_data = aggregate_entry_results(db_results, query_str)
        military_ref = aggregated_data.get("domain_knowledge") or enrich_linguistic_context(query_str, compounds)

        # 3. Resolve Dependent Entry & Hierarchy
        dependent_info = resolve_dependent_entry(query_str) or resolve_bound_descriptors(query_str, db_results)

        # 4. Educational Card Formulation
        ling_ctx_dict = digestion.linguistic_context.model_dump(by_alias=True)
        educational_card = build_educational_card(
            query_str=query_str,
            ling_ctx=ling_ctx_dict,
            is_official=is_official,
            resolved_variant=resolved_variant
        )

        # Build fallback result item for unlisted terms if db_results empty
        if not db_results:
            ling_analysis = parse_khmer_linguistics(query_str, "", is_official=False)
            db_results = [{
                "id": "unlisted_1",
                "entry_km": query_str,
                "ipa_km": ling_analysis.get("phonetics", {}).get("primary_ipa", f"/{query_str}/"),
                "definition_km": f"ពាក្យ '{query_str}' មិនទាន់មានក្នុងទិន្នន័យវចនានុក្រមផ្លូវការនៅឡើយទេ។ ទិន្នន័យនេះត្រូវបានកត់ត្រាទុកសម្រាប់បកប្រែ និងបញ្ចូលក្នុងកំណែទម្រង់ក្រោយ។",
                "definitions_list": [f"ពាក្យ '{query_str}' មិនទាន់មានក្នុងទិន្នន័យវចនានុក្រមផ្លូវការនៅឡើយទេ។"],
                "source": "ពាក្យមិនទាន់កត់ត្រា (Unlisted Entry)",
                "pos": "unlisted",
                "pos_full": "Unlisted"
            }]

        # Build detailed SearchResultItem objects for compound entries
        compound_entries_list = []
        for c_idx, comp in enumerate(compounds):
            headword_ling = parse_khmer_linguistics(comp["word"], comp["definition"], is_official=True)
            ipa_val = headword_ling.get("phonetics", {}).get("primary_ipa", f"/{comp['word']}/")
            compound_entries_list.append({
                "id": f"comp_entry_{c_idx + 1}",
                "entry_km": comp["word"],
                "ipa_km": ipa_val,
                "definition_km": comp["definition"],
                "definitions_list": format_numbered_definitions(comp["definition"]),
                "source": "សមាសសព្ទ / ពាក្យផ្សំ (Compound Derivative)",
                "pos": comp["pos"],
                "pos_full": comp["pos"]
            })

        raw_def = db_results[0]["definition_km"] if db_results else ""
        ling_analysis = parse_khmer_linguistics(query_str, raw_def, is_official=is_official)

        return SearchResponse(
            query=query_str,
            grapheme_count=len(query_str),
            status=status_code,
            is_official_chuon_nath=is_official,
            total=len(db_results) if is_official else 0,
            resolved_variant=resolved_variant,
            educational_card=educational_card,
            linguistic_analysis=ling_analysis,
            linguistic_context=ling_ctx_dict,
            results=db_results,
            compound_terms=compounds,
            compound_entries=compound_entries_list,
            military_reference=military_ref,
            predictive_suggestions=predictive_candidates,
            composite_analysis=composite_res.model_dump()
        )

    except Exception as e:
        logger.error(f"Search endpoint failure for '{query_str}': {e}")
        return SearchResponse(
            query=query_str,
            grapheme_count=len(query_str),
            status="error",
            is_official_chuon_nath=False,
            total=0,
            resolved_variant=None,
            educational_card=EducationalCard(
                title_km="កំណត់ចំណាំ",
                register_label_km="មានបញ្ហាបច្ចេកទេស",
                historical_context_km="មានបញ្ហា",
                is_chuon_nath_official=False
            ),
            linguistic_analysis=parse_khmer_linguistics(query_str, "", is_official=False),
            results=[{
                "id": "err",
                "entry_km": query_str,
                "ipa_km": f"/{query_str}/",
                "definition_km": "បញ្ហាបច្ចេកទេស",
                "definitions_list": ["បញ្ហាបច្ចេកទេស"],
                "source": "មិនប្រាកដ",
                "pos": "unknown",
                "pos_full": "Unknown"
            }],
            compound_terms=[],
            military_reference=None,
            predictive_suggestions=[],
            composite_analysis=None
        )
