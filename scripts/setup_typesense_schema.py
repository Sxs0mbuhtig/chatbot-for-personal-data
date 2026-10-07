import os
import sys
import typesense

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings

def get_typesense_client():
    return typesense.Client({
        'nodes': [{
            'host': settings.TYPESENSE_HOST,
            'port': settings.TYPESENSE_PORT,
            'protocol': 'http'
        }],
        'api_key': settings.TYPESENSE_API_KEY,
        'connection_timeout_seconds': 5
    })

def get_schema_definition(collection_name: str = None) -> dict:
    name = collection_name or settings.TYPESENSE_COLLECTION
    return {
        "name": name,
        "fields": [
            {"name": "headword", "type": "string", "infix": True},
            {"name": "norm_headword", "type": "string", "infix": True},
            {"name": "canonical_headword", "type": "string", "optional": True, "infix": True},
            {"name": "pos", "type": "string", "facet": True, "optional": True},
            {"name": "definition", "type": "string"},
            {"name": "source_title", "type": "string", "facet": True},
            {"name": "is_official_chuon_nath", "type": "bool", "optional": True, "facet": True},
            {"name": "is_variant", "type": "bool", "optional": True, "facet": True},
            {"name": "is_unofficial", "type": "bool", "optional": True, "facet": True},
            {"name": "orthographic_warning", "type": "string", "optional": True},
            {"name": "chuon_nath_guidance", "type": "string", "optional": True},
            {"name": "phonetic_ipa", "type": "string", "optional": True},
            {"name": "phonetic_km", "type": "string", "optional": True},
            {"name": "roots", "type": "string[]", "optional": True},
            {"name": "variants", "type": "string[]", "optional": True, "infix": True},
            {"name": "vector_embedding", "type": "float[]", "num_dim": 384, "optional": True},
            {"name": "sort_index", "type": "int32"}
        ],
        "default_sorting_field": "sort_index"
    }


SYNONYM_CLUSTERS = [
    {
        "id": "kamnot_orthography_cluster",
        "synonyms": ["កំណត់ត្រា", "កំនត់ត្រា", "កម្នត់ត្រា"]
    },
    {
        "id": "kantrai_orthography_cluster",
        "synonyms": ["កន្ត្រៃ", "កន់ត្រៃ"]
    },
    {
        "id": "chamnong_orthography_cluster",
        "synonyms": ["ចំណង់", "ចំនង់"]
    },
    {
        "id": "damrong_orthography_cluster",
        "synonyms": ["តម្រង់", "ដំរង់"]
    },
    {
        "id": "computer_orthography_cluster",
        "synonyms": ["កុំព្យូទ័រ", "កុមព្យូទ័រ"]
    }
]

def setup_typesense_collection(client=None, recreate: bool = False):
    client = client or get_typesense_client()
    collection_name = settings.TYPESENSE_COLLECTION
    schema = get_schema_definition(collection_name)

    try:
        if recreate:
            client.collections[collection_name].delete()
            print(f"Deleted existing collection '{collection_name}'.")
            client.collections.create(schema)
            print(f"Created collection '{collection_name}'.")
        else:
            client.collections[collection_name].retrieve()
            print(f"Collection '{collection_name}' already exists.")
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(schema)
        print(f"Created collection '{collection_name}'.")
    except Exception as e:
        print(f"Typesense connection warning: {e}")
        return False

    for rule in SYNONYM_CLUSTERS:
            syn_id = rule["id"]
            payload = {
                "synonyms": rule["synonyms"]
            }
            try:
                client.collections[collection_name].synonyms.upsert(syn_id, payload)
                print(f"Registered synonym cluster: {syn_id}")
            except Exception as e:
                print(f"Failed to register synonym '{syn_id}': {e}")

    return True

if __name__ == "__main__":
    setup_typesense_collection(recreate=False)
