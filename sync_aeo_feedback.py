import json
import os
import time
from services.lexicon import ts_client, COLLECTION_NAME

UNMATCHED_FILE = "unmatched_queries.json"

# Blacklist invalid compounds/typos from being auto-indexed into AEO
INVALID_TYPOS = {
    "ចែសដឹង": "ចេះដឹង"  # Maps invalid typo to suggestion
}

def process_unmatched_telemetry():
    if not os.path.exists(UNMATCHED_FILE):
        print("No unmatched queries log found.")
        return

    with open(UNMATCHED_FILE, "r", encoding="utf-8") as f:
        unmatched = json.load(f)

    frequently_requested = [
        item for item in unmatched.values() 
        if item.get("count", 0) >= 3 and item.get("status") == "pending_ai_review"
    ]

    print(f"Found {len(frequently_requested)} terms ready for review.")

    for item in frequently_requested:
        term = item["query"]
        
        # Guard against invalid typos
        if term in INVALID_TYPOS:
            item["status"] = "rejected_typo"
            item["suggested_correction"] = INVALID_TYPOS[term]
            print(f"Rejected invalid typo term '{term}'. Suggested correction: '{INVALID_TYPOS[term]}'")
            continue

        doc = {
            "headword": term,
            "norm_headword": term,
            "canonical_headword": term,
            "pos": "ន.",
            "definition": f"ពាក្យ «{term}» ត្រូវ​បាន​បន្ថែម​ស្វ័យប្រវត្តិ​ពី AEO Telemetry Feedback Engine",
            "source_title": "AEO Feedback Engine Auto-Index",
            "is_official_chuon_nath": False,
            "is_variant": False,
            "sort_index": int(time.time())
        }
        
        try:
            ts_client.collections[COLLECTION_NAME].documents.upsert(doc)
            item["status"] = "auto_indexed_aeo"
            print(f"Successfully indexed '{term}' into Typesense AEO dataset.")
        except Exception as e:
            print(f"Failed to index '{term}': {e}")

    with open(UNMATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    process_unmatched_telemetry()
