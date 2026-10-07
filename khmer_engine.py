import re
import unicodedata2 as unicodedata
from typing import Dict, List, Any, Optional
from rapidfuzz import process, fuzz

# Try importing khmer-nltk for unspaced multi-word segmentation
try:
    from khmernltk import word_tokenize
    HAS_KHMER_NLTK = True
except ImportError:
    HAS_KHMER_NLTK = False

# Sample Lexicon Array (Simulating Chuon Nath structured entries)
DATASET: List[Dict[str, Any]] = [
    {
        "id": 1,
        "headword": "កម្ពុជា",
        "pos": "ន.",
        "definition": "ឈ្មោះប្រទេសមួយនៅអាស៊ីអាគ្នេយ៍។",
    },
    {
        "id": 2,
        "headword": "ការងារ",
        "pos": "ន.",
        "definition": "អំពើ, មុខរបរ, កិច្ចការដែលត្រូវធ្វើ។",
    },
    {
        "id": 3,
        "headword": "ការអប់រំ",
        "pos": "ន.",
        "definition": "ការទូន្មាន, ការបង្ហាត់បង្រៀនចំណេះដឹង និងចរិយាធម៌។",
    },
    {
        "id": 4,
        "headword": "ផ្លូវចិត្ត",
        "pos": "ន.",
        "definition": "សន្តានចិត្ត, គំនិត ឬអារម្មណ៍ខាងក្នុង។",
    },
    {
        "id": 5,
        "headword": "កុមារ",
        "pos": "ន.",
        "definition": "ក្មេងប្រុស, ក្មេងតូច។",
    },
]


class KhmerNormalizer:
    """Normalizes Khmer Unicode string variants and strips invisible byte markers."""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""
        # 1. Canonical Unicode Composition (NFC)
        text = unicodedata.normalize("NFC", text)
        # 2. Strip Zero-Width Spaces, Non-Breaking Spaces, and Soft Hyphens
        text = re.sub(r"[\u200b\u00a0\u00ad]", "", text)
        # 3. Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text


class IntelligentKhmerSearch:
    def __init__(self, entries: List[Dict[str, Any]]):
        self.normalizer = KhmerNormalizer()
        self.index: Dict[str, Dict[str, Any]] = {}
        self.headwords: List[str] = []

        # Build Index Map
        # Handle variable dictionary schemas safely
        for entry in entries:
            hw = entry.get("headword") or entry.get("t_main") or entry.get("word", "")
            if hw:
                norm_hw = self.normalizer.clean(hw)
                self.index[norm_hw] = entry
                self.headwords.append(norm_hw)

    def tokenize_compound(self, text: str) -> List[str]:
        """Segments unspaced input strings into candidate tokens."""
        clean_text = self.normalizer.clean(text)
        if HAS_KHMER_NLTK:
            return word_tokenize(clean_text)
        # Fallback split on whitespace if segmentation library is unavailable
        return clean_text.split()

    def query(self, raw_input: str, fuzzy_threshold: float = 75.0) -> Dict[str, Any]:
        """Executes a multi-stage search resolution pass."""
        cleaned_query = self.normalizer.clean(raw_input)
        
        output = {
            "query": cleaned_query,
            "tokens": [],
            "exact_matches": [],
            "prefix_matches": [],
            "fuzzy_suggestions": []
        }

        if not cleaned_query:
            return output

        # Stage 1: Check Exact Match on full input
        if cleaned_query in self.index:
            output["exact_matches"].append(self.index[cleaned_query])
            return output

        # Stage 2: Tokenize unspaced multi-word queries
        tokens = self.tokenize_compound(cleaned_query)
        output["tokens"] = tokens

        for token in tokens:
            if token in self.index and self.index[token] not in output["exact_matches"]:
                output["exact_matches"].append(self.index[token])

        # Stage 3: Prefix Matches
        for hw in self.headwords:
            if hw.startswith(cleaned_query) and self.index[hw] not in output["prefix_matches"]:
                output["prefix_matches"].append(self.index[hw])

        # Stage 4: Fuzzy Fallback if no exact/prefix hits found
        if not output["exact_matches"] and not output["prefix_matches"]:
            matches = process.extract(
                cleaned_query,
                self.headwords,
                scorer=fuzz.ratio,
                limit=3
            )
            for hw, score, _ in matches:
                if score >= fuzzy_threshold:
                    output["fuzzy_suggestions"].append({
                        "score": score,
                        "entry": self.index[hw]
                    })

        return output


if __name__ == "__main__":
    engine = IntelligentKhmerSearch(DATASET)

    print("==================================================")
    print("Test 1: Search string containing hidden ZWSP (កម្ពុជា\\u200b)")
    print("==================================================")
    res1 = engine.query("កម្ពុជា\u200b")
    for item in res1["exact_matches"]:
        print(f"-> Found [{item['headword']}]: {item['definition']}")

    print("\n==================================================")
    print("Test 2: Unspaced Compound Input (ការអប់រំផ្លូវចិត្ត)")
    print("==================================================")
    res2 = engine.query("ការអប់រំផ្លូវចិត្ត")
    print(f"Segmented Tokens: {res2['tokens']}")
    for item in res2["exact_matches"]:
        print(f"-> Matched Component [{item['headword']}]: {item['definition']}")

    print("\n==================================================")
    print("Test 3: Near-miss Typo Fallback (កុមារា)")
    print("==================================================")
    res3 = engine.query("កុមារា")
    for item in res3["fuzzy_suggestions"]:
        print(f"-> Suggestion [{item['entry']['headword']}] (Match Score: {item['score']}%)")
