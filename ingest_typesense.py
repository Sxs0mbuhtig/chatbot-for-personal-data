import json
import re
import typesense
import unicodedata2 as unicodedata

client = typesense.Client({
    'nodes': [{
        'host': 'localhost',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'xyz_secret_key_123',
    'connection_timeout_seconds': 10
})

# Clean Schema: Stripped invalid token_separators rule
schema = {
    'name': 'dictionary',
    'fields': [
        {'name': 'headword', 'type': 'string', 'infix': True},
        {'name': 'norm_headword', 'type': 'string', 'infix': True},
        {'name': 'pos', 'type': 'string', 'optional': True},
        {'name': 'definition', 'type': 'string'}
    ]
}

# Delete collection if it exists
try:
    client.collections['dictionary'].delete()
except Exception:
    pass

client.collections.create(schema)

def clean_khmer(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    # Remove parenthetical annotations, e.g., "ក (ន.)" -> "ក"
    text = re.sub(r"\s*\(.*?\)", "", text)
    # Remove invisible spaces, soft hyphens, and whitespace noise
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
        'headword': hw,
        'norm_headword': clean_khmer(hw),
        'pos': pos,
        'definition': defn
    })

# Batch import
client.collections['dictionary'].documents.import_(documents, {'action': 'create'})
print(f"Successfully indexed {len(documents)} populated records into Typesense!")
