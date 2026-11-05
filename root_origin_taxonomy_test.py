#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv

load_dotenv("/home/sam_workstation/km_lexicon/.env")
api_key = os.getenv("TYPESENSE_API_KEY", "xyz_secret_key_123")
url = os.getenv("TYPESENSE_URL", "http://127.0.0.1:8108")

doc = {
    "id": "km_computer_01",
    "canonical_form": "កុមព្យូទ័រ",
    "orthographic_variants": {
        "standard_nckl": "កុំព្យូទ័រ",
        "variant_forms": ["កុមព្យូទ័រ", "កុំព្យុទ័រ"]
    },
    "root_origin_taxonomy": [
        {
            "source_language": "English",
            "etymon": "computer",
            "notes": "Adopted in early modern era; adapted with 'កុម-' prefix to avoid confusion with negative particle 'កុំ'."
        }
    ],
    "cross_linguistic_cognates": [
        {
            "language": "Thai",
            "cognate": "คอมพิวเตอร์"
        }
    ]
}

res = requests.post(
    f"{url}/collections/km_lexicon_entries/documents",
    json=doc,
    headers={"X-TYPESENSE-API-KEY": api_key, "Content-Type": "application/json"}
)
print("Index Status:", res.status_code, res.text)
