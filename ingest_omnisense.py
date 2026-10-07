import json
import re
import os
import typesense
import unicodedata2 as unicodedata

client = typesense.Client({
    'nodes': [{'host': 'localhost', 'port': '8108', 'protocol': 'http'}],
    'api_key': 'xyz_secret_key_123',
    'connection_timeout_seconds': 15
})

schema = {
    'name': 'omnisense_lexicon',
    'fields': [
        {'name': 'headword', 'type': 'string', 'infix': True},
        {'name': 'norm_headword', 'type': 'string', 'infix': True},
        {'name': 'pos', 'type': 'string', 'optional': True, 'facet': True},
        {'name': 'definition', 'type': 'string'},
        {'name': 'source', 'type': 'string', 'facet': True},
        {'name': 'domain', 'type': 'string', 'optional': True, 'facet': True},
        {'name': 'roots', 'type': 'string[]', 'optional': True},
        {'name': 'etymology', 'type': 'string', 'optional': True}
    ]
}

def clean_khmer(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFC", str(text))
    text = re.sub(r"\s*\(.*?\)", "", text)
    text = re.sub(r"[\u200b\u00a0\u00ad.\s]", "", text)
    return text.strip()

def extract_roots(headword: str) -> list:
    prefixes = ["ក", "ដើម", "ចុង", "មាត់", "ផ្លែ", "ខ្នង", "ពោះ", "ក្បាល", "ពក"]
    for prefix in prefixes:
        if headword.startswith(prefix) and len(headword) > len(prefix):
            return [prefix, headword[len(prefix):]]
    return [headword]

def load_chuon_nath(filepath: str) -> list:
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    docs = []
    for idx, entry in enumerate(data, start=1):
        hw = str(entry.get('t_main') or '').strip()
        defn = str(entry.get('t_exp') or '').strip()
        pos = str(entry.get('t_pos') or '').strip()
        if not hw:
            continue
            
        docs.append({
            'id': f"cn_{idx}",
            'headword': hw,
            'norm_headword': clean_khmer(hw),
            'pos': pos,
            'definition': defn,
            'source': 'Chuon Nath (1967)',
            'domain': 'Classical / Literary',
            'roots': extract_roots(hw)
        })
    return docs

if __name__ == "__main__":
    try:
        client.collections['omnisense_lexicon'].delete()
    except Exception:
        pass

    client.collections.create(schema)
    docs = load_chuon_nath('chuon_nath_full.json')
    if docs:
        client.collections['omnisense_lexicon'].documents.import_(docs, {'action': 'create'})
        print(f"Successfully indexed {len(docs)} entries!")
