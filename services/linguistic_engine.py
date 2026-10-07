import re
from typing import Optional, Dict, Any, List

# Static Domain Knowledge Reference Data
MILITARY_STRUCTURE_CONTEXT: Dict[str, Dict[str, Any]] = {
    "កងពល": {
        "title": "រចនាសម្ព័ន្ធកងយោធពលខេមរភូមិន្ទ (Military Structure)",
        "explanation": "១ កងពលធំ (Division) ឬ កងពលតូច (Brigade) មានចំនួនកម្លាំងទ័ពខុសៗគ្នាទៅតាមប្រភេទកងទ័ព៖",
        "breakdown": [
            "កងពលតូច (Brigade): មានកម្លាំងចន្លោះពី ៣,០០០ នាក់ ទៅ ៥,០០០ នាក់ (ចែកចេញជាច្រើន កងវរៈសេនាតូច/វរៈ)",
            "កងពលធំ (Division): មានកម្លាំងចន្លោះពី ១០,០០០ នាក់ ទៅ ១៥,០០០ នាក់ (ប្រមូលផ្តុំដោយ ២ ទៅ ៣ កងពលតូច)",
            "កងវរៈសេនាតូច (Battalion): មានកម្លាំងចន្លោះពី ៣០០ នាក់ ទៅ ៨០០ នាក់",
            "កងអនុសេនាតូច (Company): មានកម្លាំងចន្លោះពី ៨០ នាក់ ទៅ ១៥០ នាក់"
        ],
        "source": "ក្រសួងការពារជាតិ / អគ្គបញ្ជាការដ្ឋាននៃកងយោធពលខេមរភូមិន្ទ"
    }
}


def generate_ipa_phonetics(term: str) -> str:
    """Returns standard IPA-style phonetics for given terms."""
    if not term:
        return ""
        
    ipa_dictionary: Dict[str, str] = {
        "និស្ស័យ": "nəjsaj",
        "ធម្មំ": "tʰəm-məŋ",
        "អចិន្ត្រយ័": "ʔaʔ-cən-traj",
        "អចិន្ត្រៃយ៍": "ʔaʔ-cən-traj",
        "ពាណិជ្ជកម្ម": "paa-nec-cak-kam",
        "ចំណារ": "cɑm-naar",
        "ចំណង": "cɑm-nɑɑŋ",
        "អនិច្ចា": "ʔaʔ-nec-caa",
        "មោឃ": "moo-kʰaʔ",
        "ក្រូម": "kroam",
        "កងពល": "kɑɑŋ-pɔəl",
        "កងទ័ព": "kɑɑŋ-təp",
        "សេនា": "sae-naa"
    }

    if term in ipa_dictionary:
        return f"/{ipa_dictionary[term]}/"

    return f"/{term}/"


def parse_khmer_linguistics(term: str, definition_raw: str = "", is_official: bool = True) -> Dict[str, Any]:
    """Parses morphological features, root morphemes, and phonetics from Khmer input."""
    if not term:
        return {}

    if not is_official:
        root = "មិនប្រាកដ"
        alt_reading = "មិនប្រាកដ"
        etymology_info = "Loanword / Unlisted"
    else:
        consonants = re.findall(r'[\u1780-\u17B3]', term)
        root = consonants[0] if consonants else (term[0] if term else "មិនប្រាកដ")
        alt_reading = "គ្មាន"
        
        etymology_info = None
        sanskrit_pali_markers = [
            'សាស្ត្រ', 'វិទ្យា', 'ធម្ម', 'បុរាណ', 'កិច្ច', 
            'មន្ត្រី', 'អនិច្ច', 'មោឃ', 'កាល', 'និស្ស័យ', 'សេនា'
        ]
        if any(marker in term for marker in sanskrit_pali_markers):
            etymology_info = "Sanskrit/Pali"

    ipa_phonetics = generate_ipa_phonetics(term)

    return {
        "morphology": {
            "root_morpheme": root,
            "etymology_root": etymology_info,
        },
        "phonetics": {
            "primary_ipa": ipa_phonetics,
            "alternative_reading_km": alt_reading
        }
    }


def enrich_linguistic_context(query_str: str, compounds: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Injects domain-specific contextual knowledge cards when relevant keywords are present."""
    if query_str in MILITARY_STRUCTURE_CONTEXT:
        return MILITARY_STRUCTURE_CONTEXT[query_str]
        
    for c in compounds:
        if "កងពល" in c.get("word", ""):
            return MILITARY_STRUCTURE_CONTEXT["កងពល"]
            
    return None
