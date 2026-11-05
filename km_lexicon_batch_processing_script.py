import json
import logging
import urllib.request
import urllib.error

# System Endpoints
HAPROXY_ENDPOINT = "http://127.0.0.1:11435/api/generate"
TYPESENSE_ENDPOINT = "http://127.0.0.1:8108/collections/km_lexicon_entries/documents"
TYPESENSE_API_KEY = "xyz"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

PROMPT_TEMPLATE = """[RULE SET: Hard Sub-1% Cloud Token Budget active.]
Parse and enrich the raw Khmer lexicographical entry below according to the km_lexicon audit specifications.
Handle:
1. Scriptio continua and ZWSP boundary flags.
2. Syllable classification (Live/Dead: ព្យញ្ញ្ជនៈរស់/ស្លាប់ aligned with Tai-Kadai คำเป็น/คำตาย).
3. Polysemy, multi-register sense hierarchies, and verb serialization array constructs.
4. Correct cross-linguistic etymology derivations (Pali/Sanskrit, Mon, Thai, Western Loanwords).

Raw Payload:
{raw_json_payload}

Return ONLY valid JSON matching the Typesense indexing schema.
"""

def query_local_mcp_pool(raw_payload: dict, model_target: str = "qwen2.5-coder:14b") -> dict:
    """Dispatches request via local HAProxy gateway to avoid cloud token consumption."""
    formatted_prompt = PROMPT_TEMPLATE.format(raw_json_payload=json.dumps(raw_payload, ensure_ascii=False))
    
    payload = {
        "model": model_target,
        "prompt": formatted_prompt,
        "stream": False,
        "format": "json"
    }
    
    req = urllib.request.Request(
        HAPROXY_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        logging.info(f"Offloading processing to Local MCP Pool target model: {model_target}")
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            parsed_response = res_data.get("response", "{}")
            return json.loads(parsed_response)
    except urllib.error.URLError as e:
        logging.error(f"Failed to connect to local HAProxy pool: {e}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse LLM response JSON: {e}")
        return {}

def ingest_to_typesense(enriched_doc: dict) -> bool:
    """Ingests the enriched document into Typesense database."""
    if not enriched_doc:
        logging.warning("Skipping empty document ingestion.")
        return False

    req = urllib.request.Request(
        TYPESENSE_ENDPOINT,
        data=json.dumps(enriched_doc, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-TYPESENSE-API-KEY": TYPESENSE_API_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as response:
            logging.info(f"Successfully indexed document to Typesense. Status: {response.status}")
            return True
    except urllib.error.URLError as e:
        logging.error(f"Typesense indexing failed: {e}")
        return False

def process_batch(entries: list):
    """Batch loop processor for staged lexicon definitions."""
    for raw_entry in entries:
        logging.info(f"Processing Lemma: {raw_entry.get('canonical_form', 'Unknown')}")
        enriched_data = query_local_mcp_pool(raw_entry)
        ingest_to_typesense(enriched_data)

if __name__ == "__main__":
    sample_staged_entries = [
        {
            "canonical_form": "កុំព្យូទ័រ",
            "root_origin_taxonomy": ["French/English Loan"],
            "phonological_status": {"កុំ": "ព្យញ្ញ្ជនៈរស់", "ព្យូទ័រ": "ព្យញ្ញ្ជនៈរស់"},
            "sense_hierarchy": {"register": "technical", "sense_id": "T001"},
            "orthographic_variants": {"canonical_form": "កុំព្យូទ័រ", "variant_forms": ["កុមព្យូទ័រ"]}
        }
    ]
    process_batch(sample_staged_entries)