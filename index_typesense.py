import json
import os
import typesense

try:
    from khmer_normalizer import normalize_khmer_orthography
except ImportError:
    def normalize_khmer_orthography(text: str) -> str:
        return text

TS_HOST = os.getenv("TYPESENSE_HOST", "localhost")
TS_PORT = os.getenv("TYPESENSE_PORT", "8108")
TS_KEY = os.getenv("TYPESENSE_API_KEY", "xyz_secret_key_123")

client = typesense.Client({
    'nodes': [{'host': TS_HOST, 'port': TS_PORT, 'protocol': 'http'}],
    'api_key': TS_KEY,
    'connection_timeout_seconds': 10
})

COLLECTION_NAME = "omnisense_lexicon"

# Managed Dictionary Matrix for Derivations & Orthographic Variants
LEXICON_ENTRIES = [
    {
        "id": "entry_kamnot_tra_canonical",
        "headword": "កំណត់ត្រា",
        "pos": "ន.",
        "definition": "ការកត់ត្រា, អ្វីៗដែលគេកត់ត្រាទុកជាព័ត៌មានឬឯកសារអំពីព្រឹត្តិការណ៍ រឿងរ៉ាវ ឬបញ្ហាផ្សេងៗ : កំណត់ត្រាប្រចាំថ្ងៃ, កំណត់ត្រាប្រវត្តិសាស្ត្រ។",
        "source_title": "វចនានុក្រមជួនណាត",
        "is_official_chuon_nath": True,
        "is_variant": False,
        "is_unofficial": False,
        "canonical_headword": "កំណត់ត្រា",
        "phonetic_ipa": "kɑm.nɑt.traː",
        "phonetic_km": "កំ-ណាត់-ត្រា",
        "roots": ["កត់", "ត្រា"],
        "variants": ["កំនត់ត្រា", "កម្នត់ត្រា"]
    },
    {
        "id": "entry_kamnot_tra_variant_nikahit",
        "headword": "កំនត់ត្រា",
        "pos": "ន.",
        "definition": "ការកត់ត្រា, អ្វីៗដែលគេកត់ត្រាទុកជាព័ត៌មានឬឯកសារអំពីព្រឹត្តិការណ៍ រឿងរ៉ាវ ឬបញ្ហាផ្សេងៗ : កំណត់ត្រាប្រចាំថ្ងៃ, កំណត់ត្រាប្រវត្តិសាស្ត្រ។",
        "source_title": "ទម្រង់អក្ខរាវិរុទ្ធមិនផ្លូវការ (Unofficial Variant)",
        "is_official_chuon_nath": False,
        "is_variant": True,
        "is_unofficial": True,
        "canonical_headword": "កំណត់ត្រា",
        "orthographic_warning": "សំណេរ «កំនត់ត្រា» ត្រូវបានប្រប្រើប្រាស់ក្នុងឯកសារមួយចំនួន ប៉ុន្តែមិនត្រូវបានណែនាំឱ្យប្រើប្រាស់តាមវចនានុក្រមសម្ដេចព្រះសង្ឃរាជ ជួន ណាត ឡើយ។ ទម្រង់បទដ្ឋានផ្លូវការត្រឹមត្រូវគឺ «កំណត់ត្រា» (ប្រើប្រាស់ ំណ)។",
        "chuon_nath_guidance": "ទម្រង់បទដ្ឋានផ្លូវការត្រឹមត្រូវគឺ «កំណត់ត្រា» (ប្រើប្រាស់ ំណ)។",
        "roots": ["កត់", "ត្រា"],
        "variants": []
    },
    {
        "id": "entry_kamnot_tra_typo_coeng",
        "headword": "កម្នត់ត្រា",
        "pos": "ន.",
        "definition": "ការកត់ត្រា, អ្វីៗដែលគេកត់ត្រាទុកជាព័ត៌មានឬឯកសារអំពីព្រឹត្តិការណ៍ រឿងរ៉ាវ ឬបញ្ហាផ្សេងៗ : កំណត់ត្រាប្រចាំថ្ងៃ, កំណត់ត្រាប្រវត្តិសាស្ត្រ។",
        "source_title": "ការភាន់ច្រឡំអក្ខរាវិរុទ្ធ (Typographical Error)",
        "is_official_chuon_nath": False,
        "is_variant": True,
        "is_unofficial": True,
        "canonical_headword": "កំណត់ត្រា",
        "orthographic_warning": "ពាក្យ «កម្នត់ត្រា» ជាកំហុសអក្ខរាវិរុទ្ធ (ការច្រឡំរវាងជើង «្» និងស្រៈ «ំណ»)។ សូមពិនិត្យពាក្យត្រឹមត្រូវ ៖ «កំណត់ត្រា»។",
        "chuon_nath_guidance": "សូមពិនិត្យពាក្យត្រឹមត្រូវ ៖ «កំណត់ត្រា»។",
        "roots": ["កត់", "ត្រា"],
        "variants": []
    }
]

def ensure_schema_exists(recreate: bool = False):
    schema = {
        "name": COLLECTION_NAME,
        "fields": [
            {"name": "headword", "type": "string", "infix": True},
            {"name": "norm_headword", "type": "string", "infix": True},
            {"name": "pos", "type": "string", "facet": True, "optional": True},
            {"name": "definition", "type": "string"},
            {"name": "source_title", "type": "string", "facet": True},
            {"name": "is_official_chuon_nath", "type": "bool", "optional": True, "facet": True},
            {"name": "is_variant", "type": "bool", "optional": True, "facet": True},
            {"name": "is_unofficial", "type": "bool", "optional": True, "facet": True},
            {"name": "canonical_headword", "type": "string", "optional": True, "infix": True},
            {"name": "orthographic_warning", "type": "string", "optional": True},
            {"name": "chuon_nath_guidance", "type": "string", "optional": True},
            {"name": "phonetic_ipa", "type": "string", "optional": True},
            {"name": "phonetic_km", "type": "string", "optional": True},
            {"name": "roots", "type": "string[]", "optional": True},
            {"name": "variants", "type": "string[]", "optional": True, "infix": True},
            {"name": "sort_index", "type": "int32"}
        ],
        "default_sorting_field": "sort_index"
    }

    try:
        if recreate:
            client.collections[COLLECTION_NAME].delete()
            client.collections.create(schema)
        else:
            client.collections[COLLECTION_NAME].retrieve()
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(schema)

def register_khmer_synonyms():
    """Configures one-way and multi-way synonym sets for orthographic variants."""
    synonym_rules = [
        {
            "id": "kamnot_orthography_cluster",
            "synonyms": ["កំណត់ត្រា", "កំនត់ត្រា", "កម្នត់ត្រា"]
        }
    ]

    for rule in synonym_rules:
        syn_id = rule["id"]
        try:
            # Correct API for modern typesense-python client
            client.collections[COLLECTION_NAME].synonyms.upsert(syn_id, rule)
            print(f"Registered synonym set: {syn_id}")
        except Exception as e:
            # Fallback for older client versions (v0.12 or below)
            try:
                client.synonym_sets[syn_id].upsert(rule)
            except Exception as inner_e:
                print(f"[Synonym Config Warning] Failed to register synonym set '{syn_id}': {e} | {inner_e}")

def populate_typesense():
    ensure_schema_exists(recreate=True)

    json_path = "chuon_nath_full.json"
    data = []
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

    data.extend(LEXICON_ENTRIES)
    documents = []

    for idx, doc in enumerate(data):
        headword = str(doc.get("t_main") or doc.get("headword", "")).strip()
        if not headword:
            continue

        # Map official indicator safely based on schema expectations
        is_official = doc.get("is_official_chuon_nath")
        if is_official is None:
            source = str(doc.get("source_title") or "វចនានុក្រមជួនណាត").strip()
            is_official = (not bool(doc.get("is_variant", False))) and (source == "វចនានុក្រមជួនណាត")

        payload = {
            "id": str(doc.get("id") or f"doc_{idx}"),
            "headword": headword,
            "norm_headword": normalize_khmer_orthography(headword),
            "pos": str(doc.get("t_pos") or doc.get("pos") or "ន.").strip(),
            "definition": str(doc.get("t_exp") or doc.get("definition") or "").strip(),
            "source_title": str(doc.get("source_title") or ("វចនានុក្រមជួនណាត" if is_official else "ទម្រង់អក្ខរាវិរុទ្ធមិនផ្លូវការ")).strip(),
            "is_official_chuon_nath": bool(is_official),
            "is_variant": bool(doc.get("is_variant", False)),
            "is_unofficial": bool(doc.get("is_unofficial", not is_official)),
            "sort_index": int(doc.get("sort_index", idx + 1))
        }

        # Optional schema fields
        if doc.get("canonical_headword"):
            payload["canonical_headword"] = str(doc["canonical_headword"]).strip()
        if doc.get("orthographic_warning") or doc.get("orthographic_note"):
            payload["orthographic_warning"] = str(doc.get("orthographic_warning") or doc.get("orthographic_note")).strip()
        if doc.get("chuon_nath_guidance"):
            payload["chuon_nath_guidance"] = str(doc["chuon_nath_guidance"]).strip()
        if doc.get("phonetic_ipa"):
            payload["phonetic_ipa"] = str(doc["phonetic_ipa"]).strip()
        if doc.get("phonetic_km"):
            payload["phonetic_km"] = str(doc["phonetic_km"]).strip()
        if doc.get("roots"):
            payload["roots"] = doc["roots"]
        if doc.get("variants"):
            payload["variants"] = doc["variants"]

        documents.append(payload)

    # Batch import to Typesense
    client.collections[COLLECTION_NAME].documents.import_(documents, {'action': 'emplace'})
    
    # Register synonym rules
    register_khmer_synonyms()
    print(f"Successfully indexed {len(documents)} documents to '{COLLECTION_NAME}'.")

if __name__ == "__main__":
    populate_typesense()
