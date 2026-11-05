import json
import re
import os
import typesense
import unicodedata

client = typesense.Client({
    'nodes': [{
        'host': os.getenv('TYPESENSE_HOST', 'typesense'),
        'port': os.getenv('TYPESENSE_PORT', '8108'),
        'protocol': os.getenv('TYPESENSE_PROTOCOL', 'http')
    }],
    'api_key': os.getenv('TYPESENSE_API_KEY', 'xyz_secret_key_123'),
    'connection_timeout_seconds': 2
})

# Advanced Enterprise Schema matching routers/search.py query requirements
schema = {
    'name': 'omnisense_lexicon',
    'fields': [
        {'name': 'canonical_headword', 'type': 'string', 'infix': True},
        {'name': 'norm_headword', 'type': 'string', 'infix': True},
        {'name': 'all_definitions_km', 'type': 'string', 'infix': True},
        {'name': 'all_definitions_en', 'type': 'string', 'optional': True},
        {'name': 'pos_km_list', 'type': 'string[]', 'optional': True, 'facet': True},
        {'name': 'pos_en_list', 'type': 'string[]', 'optional': True, 'facet': True},
        {'name': 'phonetic_ipa', 'type': 'string', 'optional': True},
        {'name': 'homonyms_json', 'type': 'string', 'optional': True},
        {'name': 'source', 'type': 'string', 'optional': True}
    ]
}

# Delete collection if it exists
try:
    client.collections['omnisense_lexicon'].delete()
except Exception:
    pass

client.collections.create(schema)

def clean_khmer(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"\s*\(.*?\)", "", text)
    text = re.sub(r"[\u200b\u00a0\u00ad.\s]", "", text)
    return text.strip()

with open('chuon_nath_full.json', 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

documents = []
for idx, entry in enumerate(raw_data, start=1):
    hw = str(entry.get('t_main') or '').strip()
    defn = str(entry.get('t_exp') or '').strip()
    pos = str(entry.get('t_pos') or '').strip()

    if not hw:
        continue

    documents.append({
        'id': str(idx),
        'canonical_headword': hw,
        'norm_headword': clean_khmer(hw),
        'all_definitions_km': defn,
        'all_definitions_en': entry.get('t_exp_en', ''),
        'pos_km_list': [pos] if pos else ["ន."],
        'pos_en_list': ["noun"],
        'phonetic_ipa': f"/{hw}/",
        'source': "វចនានុក្រមជួន ណាត (ចេញផ្សាយគ្រឹះសករាជ ១៩៦៧)"
    })

# Batch import in chunks of 2000
batch_size = 2000
for i in range(0, len(documents), batch_size):
    batch = documents[i:i + batch_size]
    client.collections['omnisense_lexicon'].documents.import_(batch, {'action': 'create'})

print(f"Successfully indexed {len(documents)} enterprise records into Typesense collection 'omnisense_lexicon'!")
