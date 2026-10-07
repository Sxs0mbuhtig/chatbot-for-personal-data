POS_ABBREVIATION_MAP = {
    # ថ្នាក់ពាក្យខ្មែរផ្លូវការ (Chuon Nath)
    "នាម": "ន.",
    "កិរិយា": "កិ.",
    "គុណនាម": "គុ.",
    "គុណសព្ទ": "គុ.",
    "កិរិយាវិសេសនៈ": "កិ.វិ.",
    "ធុរៈ": "ធុ.",
    "សព្វនាម": "សព្វ.",
    "ធ្យាន": "ធ្យា.",
    "អព្ពយសព្ទ": "អ.",
    "បុព្វបទ": "បុព្វ.",
    "នាមរនាប់": "ន.រនាប់",
    
    # English Equivalents
    "noun": "n.",
    "verb": "v.",
    "transitive_verb": "tv.",
    "intransitive_verb": "iv.",
    "adjective": "adj.",
    "adverb": "adv.",
    "preposition": "prep.",
    "classifier": "clf."
}

# services/pos_mapper.py

BOUND_DESCRIPTORS_REGISTRY = {
    "កង": {
        "entry_km": "កង",
        "pos": "modifier",
        "pos_full": "គុណនាម / ពាក្យកំណត់លក្ខណៈ",
        "usage_type": "bound_descriptor",
        "requires_lead_noun": ["នំ"],
        "canonical_form": "នំកង",
        "definition_km": "ដែល មាន រាង ជា រង្វង់ ឬ ជា កង (ប្រើ ចំពោះ នំ ៖ នំកង)។",
        "cultural_note": "នំកង ៖ នំ ប្រពៃណី ខ្មែរ ធ្វើ ពី ម្សៅ ដំណើប..."
    }
}

def resolve_dependent_entry(term: str) -> dict:
    """Checks if term is a bound descriptor that depends on a lead noun."""
    return BOUND_DESCRIPTORS_REGISTRY.get(term, None)

def resolve_pos_label(raw_pos: str) -> str:
    if not raw_pos:
        return "ន."
    clean = raw_pos.strip().lower()
    return POS_ABBREVIATION_MAP.get(clean, raw_pos)
