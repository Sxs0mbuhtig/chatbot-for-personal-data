# scripts/fix_blank_definitions.py

import re
from typing import Dict, List, Any

def cleanup_lexicon_database(db_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Iterates through the entire lexicon DB, cleans invalid definitions (e.g., sole '។'),
    and merges duplicate definitions for the same headword.
    """
    grouped_entries: Dict[str, Dict[str, Any]] = {}

    for entry in db_entries:
        headword = entry.get("headword", "").strip()
        raw_def = entry.get("definition", "").strip()
        
        # ត្រួតពិនិត្យមើលថាតើជាអត្ថបទខូច (មានតែសញ្ញាខណ្ឌ ឬទទេ)
        cleaned_def = re.sub(r"^[\s\u17d4\u200b\u00a0]+|[\s\u17d4\u200b\u00a0]+$", "", raw_def)

        if not cleaned_def:
            # រំលង entry ដែលគ្មានអត្ថន័យ
            continue

        if headword not in grouped_entries:
            entry["definition"] = cleaned_def
            grouped_entries[headword] = entry
        else:
            # បើមាន Headword ដូចគ្នា ធ្វើការផ្លាស់ប្តូរ ឬបន្ថែមនិយមន័យត្រឹមត្រូវបញ្ចូលគ្នា
            existing_def = grouped_entries[headword]["definition"]
            if cleaned_def not in existing_def:
                grouped_entries[headword]["definition"] = f"{existing_def}\n{cleaned_def}"

    return list(grouped_entries.values())
