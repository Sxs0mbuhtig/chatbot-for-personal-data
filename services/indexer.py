import json

def transform_curated_entry_for_typesense(curated_json: dict) -> dict:
    """Flattens nested homonym data for Typesense indexing while keeping JSON intact."""
    headword = curated_json.get("canonical_headword", "")
    homonyms = curated_json.get("homonyms", [])

    pos_km_set = set()
    pos_en_set = set()
    origins_set = set()
    registers_set = set()
    domains_set = set()

    defs_km = []
    defs_en = []

    for hom in homonyms:
        origin = hom.get("etymology", {}).get("origin_language")
        if origin:
            origins_set.add(origin)

        for sense in hom.get("senses", []):
            if sense.get("pos_km"): pos_km_set.add(sense["pos_km"])
            if sense.get("pos_en"): pos_en_set.add(sense["pos_en"])
            if sense.get("register"): registers_set.add(sense["register"])
            if sense.get("domain_category"): domains_set.add(sense["domain_category"])

            if sense.get("definition_km"): defs_km.append(sense["definition_km"])
            if sense.get("definition_en"): defs_en.append(sense["definition_en"])

    return {
        "id": f"entry_{headword}",
        "canonical_headword": headword,
        "phonetic_ipa": curated_json.get("phonetic_ipa", ""),
        "pos_km_list": list(pos_km_set),
        "pos_en_list": list(pos_en_set),
        "etymology_origins": list(origins_set),
        "registers": list(registers_set),
        "domain_categories": list(domains_set),
        "all_definitions_km": " | ".join(defs_km),
        "all_definitions_en": " | ".join(defs_en),
        # Raw nested structure preserved for UI rendering
        "homonyms_json": json.dumps(curated_json, ensure_ascii=False)
    }
