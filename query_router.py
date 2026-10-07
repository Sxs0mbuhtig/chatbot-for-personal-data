import requests

TYPESENSE_URL = "http://localhost:8108/collections/omnisense_lexicon/documents/search"
HEADERS = {"X-TYPESENSE-API-KEY": "xyz_secret_key_123"}

def search_lexicon(query_str: str):
    query_str = query_str.strip()

    # 1. Exact match lookup
    res = requests.get(TYPESENSE_URL, headers=HEADERS, params={
        "q": query_str,
        "query_by": "headword,norm_headword,canonical_headword",
        "filter_by": f"headword:={query_str} || norm_headword:={query_str}",
        "prefix": "false"
    }).json()

    if res.get("found", 0) > 0:
        doc = res["hits"][0]["document"]

        # Case A: Variant / Unofficial / Typo Entry
        if doc.get("is_variant"):
            canonical_word = doc.get("canonical_headword", "កំណត់ត្រា")
            
            # Fetch the official canonical document for proper Chuon Nath definitions
            c_res = requests.get(TYPESENSE_URL, headers=HEADERS, params={
                "q": canonical_word,
                "query_by": "headword",
                "filter_by": f"headword:={canonical_word} && is_variant:=false",
                "prefix": "false"
            }).json()

            canonical_doc = c_res["hits"][0]["document"] if c_res.get("hits") else doc

            return {
                "type": "variant_redirect",
                "searched_query": query_str,
                "is_unofficial": doc.get("is_unofficial", True),
                "orthographic_note": doc.get("orthographic_note"),
                "canonical_entry": canonical_doc
            }

        # Case B: Standard Canonical Search
        return {
            "type": "canonical_match",
            "entry": doc
        }

    # 2. Fuzzy / Infix fallback for typos like 'កម្នត់ត្រា'
    fuzzy_res = requests.get(TYPESENSE_URL, headers=HEADERS, params={
        "q": query_str,
        "query_by": "headword,norm_headword",
        "prefix": "true",
        "num_typos": 2
    }).json()

    if fuzzy_res.get("found", 0) > 0:
        target_doc = fuzzy_res["hits"][0]["document"]
        return {
            "type": "fuzzy_suggestion",
            "searched_query": query_str,
            "suggestion_note": f"ពាក្យ «{query_str}» ពុំមានក្នុងវចនានុក្រមទេ។ លទ្ធផលខាងក្រោមបង្ហាញសម្រាប់ពាក្យត្រឹមត្រូវ ៖ «{target_doc.get('canonical_headword', target_doc['headword'])}»",
            "entry": target_doc
        }

    # 3. True zero-hit fallback
    return {"type": "not_found", "searched_query": query_str}
