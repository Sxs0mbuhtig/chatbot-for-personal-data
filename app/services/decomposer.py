# app/services/decomposer.py
import re

def decompose_khmer_compound(query: str):
    """
    Decomposes compound words into root candidates.
    Example: 'កជើង' -> Prefix 'ក' (Neck/Connector) + Root 'ជើង' (Foot)
    """
    # Simple rule-based structural split demo for anatomical/spatial compounds
    prefixes = {
        "ក": "Neck / Narrow junction / Connector (អវយវៈតភ្ជាប់ ឬចំណុចរួម)",
        "ដើម": "Trunk / Base / Origin (ប្រភព ឬផ្នែកខាងដើម)",
        "ចុង": "Tip / Extremity (ផ្នែកខាងចុង)",
        "មាត់": "Mouth / Opening (ច្រកចេញចូល)",
        "ផ្លែ": "Fruit / Blade / Product (ផល ឬមុខ)"
    }
    
    for prefix, meaning in prefixes.items():
        if query.startswith(prefix) and len(query) > len(prefix):
            base_word = query[len(prefix):]
            return {
                "compound": query,
                "prefix_root": prefix,
                "prefix_meaning": meaning,
                "base_root": base_word,
                "structural_analysis": f"Compound term formed by prefix [{prefix}] + base [{base_word}]"
            }
    return None
