import re
from typing import Dict, Any, List
from services.domain_knowledge import get_domain_context

def aggregate_entry_results(raw_rows: List[Dict[str, Any]], query_str: str) -> Dict[str, Any]:
    """
    Transforms raw SQLite dictionary rows into a structured, categorized lexicon entry.
    """
    base_meanings = []
    jewelry_compounds = []
    hardware_compounds = []
    military_compounds = []
    
    # Keyword categories for pattern matching
    JEWELRY_KEYWORDS = ["គ្រឿងអលង្ការ", "ពាក់នៅនឹងក", "កជើង", "ដើមដៃ", "ពាក់ប្រហក"]
    HARDWARE_KEYWORDS = ["កងទ្រនាប់", "ខ្ចៅ", "រឹតបន្តឹង"]
    MILITARY_KEYWORDS = ["កងទ័ព", "យោធា", "កាំភ្លើងធំ", "នាវាចរណ៍", "សន្តិសុខ", "កងកម្លាំង", "អង្គភាព"]

    for row in raw_rows:
        definition = row.get("definition_km", "")
        pos = row.get("pos", "ន.")

        # 1. Hardware Category Filtering
        if any(kw in definition for kw in HARDWARE_KEYWORDS):
            hardware_compounds.append({
                "word": "កងទ្រនាប់",
                "pos": "ន.",
                "definition": definition,
                "example": "កងទ្រនាប់ខ្ចៅ, កងរឹត"
            })
        
        # 2. Jewelry Category Filtering (កងក, កងដៃ, កងជើង)
        elif any(kw in definition for kw in JEWELRY_KEYWORDS):
            word_label = query_str
            if "ក" in definition and "ដៃ" in definition:
                word_label = "កងក / កងដៃ / កងជើង"
            elif "កជើង" in definition:
                word_label = "កងជើង"
            elif "ក" in definition:
                word_label = "កងក"

            jewelry_compounds.append({
                "word": word_label,
                "pos": "ន.",
                "definition": definition
            })

        # 3. Domain / Military Category Filtering
        elif any(kw in definition for kw in MILITARY_KEYWORDS):
            military_compounds.append({
                "word": query_str,
                "pos": pos,
                "definition": definition
            })

        # 4. Base Meanings & Compound Verbs Refinement
        else:
            # ការកែសម្រួលន័យ "ចាប់កង" និង "ចាប់ត្រកង" តាម Context ច្បាស់លាស់
            if "ចាប់ត្រកង" in definition or "ចាប់កង" in definition:
                base_meanings.extend([
                    {
                        "pos": "កិ.បន្សំ",
                        "term": "ចាប់កង (ន័យទី ១)",
                        "definition": "រើស ឬជ្រើសរើសយករង្វង់/កងណាមួយ (ចាប់ = កិរិយាសព្ទសកម្ម, កង = កម្មបទ)",
                        "usage": "ប្រៀបធៀប៖ ចាប់យករង្វង់កង"
                    },
                    {
                        "pos": "កិ.បន្សំ",
                        "term": "ចាប់កង (ន័យទី ២)",
                        "definition": "ប្រមូលផ្តុំ ឬប្រមូលវត្ថុ/របស់ទ្រព្យឱ្យជុំគ្នាជាបាច់/ជាក្រុម រួចលើក ឬជម្លៀសចេញទៅជាបាច់",
                        "usage": "ប្រៀបធៀប៖ ចាប់ប្រមូលជាកង/ជាបាច់ (ប្រើលើវត្ថុ ឬរបស់របរ)"
                    },
                    {
                        "pos": "កិ.បន្សំ",
                        "term": "ចាប់ត្រកង",
                        "definition": "ចាប់ក្រសោប ឬអោបប្រកបដោយក្តីស្រឡាញ់ ក្តីខ្នាញ់ និងការថ្នម",
                        "usage": "ប្រើប្រាស់ចំពោះ៖ មនុស្ស, ទារក, ឬគូស្នេហ៍ (ខុសពី 'ចាប់កង' ដែលប្រើលើវត្ថុ)"
                    }
                ])
            elif "ធ្វើឱ្យមូលជាវង់" in definition:
                base_meanings.append({
                    "pos": "កិ.",
                    "term": "កង (ធ្វើឱ្យមូល)",
                    "definition": definition,
                    "example": "ឧទាហរណ៍ ៖ កងខ្សែ, កងវល្លិ៍"
                })
            else:
                base_meanings.append({
                    "pos": pos,
                    "term": query_str,
                    "definition": definition
                })

    # Domain Knowledge integration for military terms
    domain_card = None
    if military_compounds:
        domain_card = get_domain_context("កងពល") or get_domain_context(query_str)

    return {
        "headword": query_str,
        "primary_definitions": base_meanings,
        "categories": {
            "jewelry_group": {
                "title": "គ្រឿងអលង្ការ និងគ្រឿងពាក់ (Jewelry & Wearables)",
                "items": jewelry_compounds
            },
            "hardware_group": {
                "title": "គ្រឿងទម្រ និងគ្រឿងប្រដាប់ (Hardware & Fittings)",
                "items": hardware_compounds
            }
        },
        "domain_knowledge": domain_card
    }

# services/lexicon_aggregator.py

LEAD_NOUN_HIERARCHY = {
    "នំ": {
        "entry_km": "នំ",
        "pos": "noun",
        "category": "culinary",
        "sub_types": [
            {
                "descriptor": "កង",
                "full_term": "នំកង",
                "shape_type": "ring_shaped",
                "texture": "chewy / glutinous",
                "glaze": "caramelized palm sugar & white sesame"
            },
            {
                "descriptor": "គ្រក់",
                "full_term": "នំគ្រក់"
            }
        ]
    }
}

def get_lead_noun_context(term: str) -> dict:
    """Returns hierarchy structure if term is a known lead noun."""
    return LEAD_NOUN_HIERARCHY.get(term, None)
