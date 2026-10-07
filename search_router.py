import json
from typesense import Client
from khmer_normalizer import normalize_khmer_orthography

def search_lexicon(query_text: str, client: Client):
    # Tier 1: Exact Match Query
    search_params = {
        'q': query_text,
        'query_by': 'headword,norm_headword',
        'infix': 'always',
        'per_page': 1
    }
    
    results = client.collections['omnisense_lexicon'].documents.search(search_params)
    
    if results['found'] > 0:
        return {"status": "exact_match", "data": results['hits'][0]['document']}

    # Tier 2: Normalized Search (Handles ន/ណ, ដ/ត swaps)
    norm_query = normalize_khmer_orthography(query_text)
    search_params['q'] = norm_query
    
    norm_results = client.collections['omnisense_lexicon'].documents.search(search_params)
    
    if norm_results['found'] > 0:
        match = norm_results['hits'][0]['document']
        
        # Check if matched entry contains Chuon Nath directive or variant flagging
        return {
            "status": "variant_redirect",
            "searched_query": query_text,
            "canonical_word": match.get("headword"),
            "directive": match.get("orthographic_directive", f"ពាក្យត្រឹមត្រូវតាមអក្ខរាវិរុទ្ធគឺ «{match.get('headword')}»"),
            "data": match
        }

    # Tier 3: GenAI Fallback for Complex Compounds & Misspellings
    return trigger_genai_analysis(query_text)

def trigger_genai_analysis(query_text: str):
    """
    System prompt for LLM when word is absent in static index.
    """
    system_prompt = f"""
    You are Samdach Chuon Nath Lexicographical AI Agent.
    The user searched for: "{query_text}"
    
    Analyze:
    1. Identify if this is a misspelling due to phonetic substitution (e.g., ន vs ណ, ំ vs ម, ដ vs ត).
    2. Provide the canonical spelling according to standard Khmer orthography / Chuon Nath rules.
    3. Break down the morphology (Prefix, Infix, Root) if applicable.
    4. Provide the definition and usage guidance.
    """
    
    # Send system_prompt to LLM endpoint...
    return {"status": "genai_analyzed", "query": query_text}
