from typing import Dict, Any, Optional

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

def get_domain_context(term: str) -> Optional[Dict[str, Any]]:
    """Retrieves contextual reference cards for specific technical/domain terms."""
    return MILITARY_STRUCTURE_CONTEXT.get(term)
