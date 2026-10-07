import json
import os
import time
from datetime import datetime, timezone
from services.lexicon import ts_client, COLLECTION_NAME

UNMATCHED_FILE = "unmatched_queries.json"

# 1. Clean unmatched_queries.json (remove typo compound 'ចែសដឹង')
if os.path.exists(UNMATCHED_FILE):
    with open(UNMATCHED_FILE, "r", encoding="utf-8") as f:
        unmatched = json.load(f)
    if "ចែសដឹង" in unmatched:
        del unmatched["ចែសដឹង"]
    
    # Stage valid 'ចេះដឹង' correctly
    now_utc = datetime.now(timezone.utc).isoformat()
    unmatched["ចេះដឹង"] = {
        "query": "ចេះដឹង",
        "count": 5,
        "first_logged": now_utc,
        "last_logged": now_utc,
        "status": "pending_ai_review"
    }
    with open(UNMATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, ensure_ascii=False, indent=2)

# 2. Seed explicit, correct entries into Typesense
valid_entries = [
    {
        "headword": "ចេះដឹង",
        "norm_headword": "ចេះដឹង",
        "canonical_headword": "ចេះដឹង",
        "pos": "គុ./កិ.",
        "definition": "ដែលមានចំណេះដឹង, យល់ដឹងខុសត្រូវ, មានការអប់រំ។",
        "source_title": "វចនានុក្រមខ្មែរ / Khmer Lexicon",
        "is_official_chuon_nath": True,
        "is_variant": False,
        "sort_index": int(time.time())
    },
    {
        "headword": "ចែស",
        "norm_headword": "ចែស",
        "canonical_headword": "ចែស",
        "pos": "គុ./កិ.គុ.",
        "definition": "១. ពាក្យសម្រាប់ផ្សំជួយបញ្ជាក់ន័យអោយរឹតតែច្បាស់ (ឧ. ច្បាស់ចែស, ភ្លឺចែស)។ ២. សូរសំឡេងទង្គិចលោហធាតុខ្លាំងស្រួចរំខានត្រចៀក (ឧ. ចែសៗ, ចែសចែសចែស)។",
        "source_title": "វចនានុក្រមជួនណាត",
        "is_official_chuon_nath": True,
        "is_variant": False,
        "sort_index": int(time.time()) + 1
    }
]

for doc in valid_entries:
    ts_client.collections[COLLECTION_NAME].documents.upsert(doc)
    print(f"Successfully indexed entry: {doc['headword']}")
