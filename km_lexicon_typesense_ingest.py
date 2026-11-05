# km_lexicon_typesense_ingest.py
import json
import requests

# Local HAProxy Gateway & Typesense Configuration
HA_PROXY_URL = "http://127.0.0.1:11435/api/generate"
TYPESENSE_URL = "http://127.0.0.1:8108/collections/km_lexicon_entries/documents"
HEADERS = {"X-TYPESENSE-API-KEY": "xyz", "Content-Type": "application/json"}

def parse_entry_via_local_ai(raw_json):
    payload = {
        "model": "qwen2.5-coder:14b",
        "prompt": f"Normalize and structure this JSON for Typesense indexing adhering to the audit requirements (scriptio continua, ZWSP, live/dead syllables): {json.dumps(raw_json)}",
        "stream": False
    }
    response = requests.post(HA_PROXY_URL, json=payload)
    return response.json()

if __name__ == "__main__":
    print("Ingestion pipeline initialized via local HAProxy gateway.")
