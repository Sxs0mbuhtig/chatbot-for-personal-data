import re
import unicodedata2 as unicodedata

# Khmer Unicode Code Point Sets
KHMER_BASE_CONSONANTS = set(chr(c) for c in range(0x1780, 0x17B4))
KHMER_CONSONANT_SHIFTERS = {"\u17c9", "\u17ca"}  # ត្រីសព្ទ, មូសិកទន្ត
KHMER_DEPENDENT_VOWELS = set(chr(c) for c in range(0x17b6, 0x17c6))
KHMER_DIACRITICS = set(chr(c) for c in range(0x17c6, 0x17d4)) - KHMER_CONSONANT_SHIFTERS
KHMER_LEK_TO = "\u17d7"  # ៗ

# Classical <-> Modern Independent Vowel & Phonetic Mapping Dictionary
INDEPENDENT_VOWEL_MAP = {
    "ឮ": ["លឺ"],
    "លឺ": ["ឮ"],
    "រឭក": ["រលឹក", "រំលឹក"],
    "រលឹក": ["រឭក"],
    "រំលឹក": ["រឭក"],
    "ឫស": ["រឹស"],
    "រឹស": ["ឫស"],
}

def clean_khmer_text(text: str) -> str:
    """
    Performs NFC Unicode normalization and strips invisible byte markers:
    Zero-Width Space (U+200B), Non-Breaking Space (U+00A0), Soft Hyphen (U+00AD).
    """
    if not text:
        return ""
    # 1. Canonical Unicode Composition (NFC)
    text = unicodedata.normalize("NFC", text)
    # 2. Strip Zero-Width Spaces, Non-Breaking Spaces, and Soft Hyphens
    text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)
    # 3. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

def reorder_khmer_syllable_components(syllable: str) -> str:
    """
    Reorders a single Khmer syllable cluster into strict canonical Unicode sequence:
    Base Consonant -> Consonant Shifter -> Subscripts (Coeng + Consonant) -> Dependent Vowels -> Diacritics/Signs
    """
    if not syllable:
        return ""

    base = ""
    shifter = ""
    subscripts = []
    vowels = []
    diacritics = []

    i = 0
    n = len(syllable)

    while i < n:
        char = syllable[i]
        if char == "\u17d2":  # Coeng (ជើង)
            if i + 1 < n:
                subscripts.append(char + syllable[i + 1])
                i += 2
                continue
            else:
                subscripts.append(char)
                i += 1
                continue
        elif char in KHMER_CONSONANT_SHIFTERS:
            shifter += char
        elif char in KHMER_DEPENDENT_VOWELS:
            vowels.append(char)
        elif char in KHMER_DIACRITICS:
            diacritics.append(char)
        else:
            if not base:
                base = char
            else:
                vowels.append(char)
        i += 1

    return base + shifter + "".join(subscripts) + "".join(vowels) + "".join(diacritics)

def normalize_khmer_unicode(text: str) -> str:
    """
    Full canonical Khmer Unicode normalizer:
    Strips invisible byte markers, applies NFC, and reorders syllable components canonically.
    """
    cleaned = clean_khmer_text(text)
    if not cleaned:
        return ""
    
    syllable_pattern = re.compile(
        r"[\u1780-\u17b3][\u17c9\u17ca]?(?:\u17d2[\u1780-\u17b3])*(?:[\u17b6-\u17c5])*(?:[\u17c6-\u17d3])*"
    )
    
    parts = []
    last_idx = 0
    for m in syllable_pattern.finditer(cleaned):
        start, end = m.span()
        if start > last_idx:
            parts.append(cleaned[last_idx:start])
        syllable_text = m.group(0)
        parts.append(reorder_khmer_syllable_components(syllable_text))
        last_idx = end
    
    if last_idx < len(cleaned):
        parts.append(cleaned[last_idx:])
        
    return "".join(parts)

def get_independent_vowel_variants(text: str) -> list[str]:
    """
    Generates classical <-> modern independent vowel bridging variants.
    (e.g., ឮ <-> លឺ, រឭក <-> រលឹក/រំលឹក, ឫស <-> រឹស).
    """
    clean = clean_khmer_text(text)
    variants = set()
    if clean in INDEPENDENT_VOWEL_MAP:
        variants.update(INDEPENDENT_VOWEL_MAP[clean])
    
    for src, targets in INDEPENDENT_VOWEL_MAP.items():
        if src in clean:
            for tgt in targets:
                variants.add(clean.replace(src, tgt))
    return list(variants)

def extract_echo_roots(text: str) -> list[str]:
    """
    Splits reduplicated compounds into constituent root syllables and full text.
    (e.g., ងីងើ -> ['ងី', 'ងើ', 'ងីងើ'], តេងតាងៗ -> ['តេង', 'តាង', 'តេងតាង']).
    """
    if not text:
        return []
    clean = clean_khmer_text(text)
    root_text = re.sub(r"[\s\u17d7]+$", "", clean).strip()
    
    n = len(root_text)
    if n >= 4 and n % 2 == 0:
        half = n // 2
        s1, s2 = root_text[:half], root_text[half:]
        if s1 and s2:
            return [s1, s2, root_text]
            
    return [root_text]


def count_khmer_graphemes(text: str) -> int:
    """
    Accurately counts Khmer visual grapheme clusters instead of raw code points.
    A single Khmer grapheme cluster consists of a base consonant and its attached Coeng feet, vowels, and diacritics.
    Counts U+17D7 (លេខទោ / ៗ) as an independent grapheme token.
    """
    if not text:
        return 0
    clean = clean_khmer_text(text)
    clusters = re.findall(
        r"\u17d7|[\u1780-\u17b3][\u17c9\u17ca]?(?:\u17d2[\u1780-\u17b3])*(?:[\u17b6-\u17c5])*(?:[\u17c6-\u17d3])*|[^\u1780-\u17b3]",
        clean
    )
    return len([c for c in clusters if c.strip()])

def sanitize_khmer_punctuation(text: str) -> str:
    """
    Orthographic Punctuation & Spacing Sanitizer for Khmer script:
    1. Replaces every loan comma (,) not followed by a space with ', '.
    2. Strips dangling colons (:) and trailing whitespace from definition strings.
    3. Contextual sentence termination:
       - Complete sentences / independent thoughts (length >= 15 or containing verb markers) terminate with '។' (U+17D8 Khan).
       - Short phrases, fragments, or POS labels leave trailing edge clean without dangling colons/periods.
    """
    if not text:
        return ""
    
    # 1. Fix Loan Commas: replace ',' not followed by space with ', '
    text = re.sub(r",(?!\s)", ", ", text)
    
    # 2. Strip dangling colons (:), periods, and trailing whitespace
    text = re.sub(r"[:\.\s]+$", "", text).strip()
    
    # 3. Contextual Sentence Termination
    # If text ends with Khmer Khan (។), keep it intact
    if text.endswith("។"):
        return text
        
    # Check if text forms a complete sentence / independent clause (e.g. length >= 15 or contains Khmer punctuation/conjunctions)
    if len(text) >= 15 or any(k in text for k in ["ដែល", "គឺ", "ជា", "មាន", "បាន", "ត្រូវបាន"]):
        text = text + "។"
        
    return text

def normalize_khmer_orthography(text: str) -> str:
    """
    Canonical orthography normalizer.
    Deprecates destructive character substitutions ('ន'->'ណ') to prevent text corruption,
    delegating to safe canonical Unicode syllable reordering.
    """
    return normalize_khmer_unicode(text)


