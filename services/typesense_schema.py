import typesense

client = typesense.Client({
    'nodes': [{
        'host': 'khmer_dict_typesense',
        'port': '8108',
        'protocol': 'http'
    }],
    'api_key': 'xyz',
    'connection_timeout_seconds': 2
})

lexicon_schema = {
    'name': 'km_lexicon_entries',
    'fields': [
        {'name': 'id', 'type': 'string'},
        {'name': 'canonical_headword', 'type': 'string', 'facet': True},
        {'name': 'phonetic_ipa', 'type': 'string'},
        
        # Facetable lists across all homonyms for filtering
        {'name': 'pos_km_list', 'type': 'string[]', 'facet': True},
        {'name': 'pos_en_list', 'type': 'string[]', 'facet': True},
        {'name': 'etymology_origins', 'type': 'string[]', 'facet': True},
        {'name': 'registers', 'type': 'string[]', 'facet': True},
        {'name': 'domain_categories', 'type': 'string[]', 'facet': True},
        
        # Concatenated definitions for keyword search
        {'name': 'all_definitions_km', 'type': 'string'},
        {'name': 'all_definitions_en', 'type': 'string'},
        
        # Dual-language Vector Embeddings (768 dimensions for standard text-embeddings)
        {
            'name': 'definition_km_vec',
            'type': 'float[]',
            'num_dim': 768,
            'optional': True
        },
        {
            'name': 'definition_en_vec',
            'type': 'float[]',
            'num_dim': 768,
            'optional': True
        },
        
        # Raw nested JSON stored for rendering UI entry cards
        {'name': 'homonyms_json', 'type': 'string', 'index': False}
    ],
    'default_sorting_field': 'canonical_headword'
}

def reindex_schema():
    try:
        client.collections['km_lexicon_entries'].delete()
    except Exception:
        pass
    client.collections.create(lexicon_schema)
    print("✓ Created 'km_lexicon_entries' Typesense collection with dual vector support.")

if __name__ == "__main__":
    reindex_schema()
