# utils/formatting.py
import re
import urllib.parse
import unicodedata2 as unicodedata

def clean_khmer(text: str) -> str:
    if not text:
        return ""
    text = urllib.parse.unquote(text)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)
    return text.strip()

def format_document(doc: dict) -> dict:
    if not isinstance(doc, dict):
        return {}

    headword = doc.get("headword", "")
    is_official = doc.get("is_official_chuon_nath")
    
    if is_official is None:
        is_official = not doc.get("is_variant", False) and doc.get("source_title") == "វចនានុក្រមជួនណាត"

    return {
        "headword": headword,
        "canonical_headword": doc.get("canonical_headword") or headword,
        "pos": doc.get("pos") or "ន.",
        "definition": doc.get("definition") or "មិនមានការពន្យល់",
        "source_title": doc.get("source_title") or ("វចនានុក្រមជួនណាត" if is_official else "ទម្រង់អក្ខរាវិរុទ្ធមិនផ្លូវការ"),
        "is_official_chuon_nath": bool(is_official),
        "is_variant": bool(doc.get("is_variant", False)),
        "orthographic_warning": doc.get("orthographic_warning") or doc.get("chuon_nath_guidance") or "",
        "chuon_nath_guidance": doc.get("chuon_nath_guidance") or "",
        "phonetic_ipa": doc.get("phonetic_ipa", ""),
        "phonetic_km": doc.get("phonetic_km", ""),
        "roots": doc.get("roots") if isinstance(doc.get("roots"), list) else [],
        "variants": doc.get("variants") if isinstance(doc.get("variants"), list) else []
    }
    
