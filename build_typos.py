import json
import unicodedata
from collections import Counter
from rapidfuzz import process, fuzz

UNMATCHED_FILE = "./unmatched_queries.jsonl"
VALID_WORDS_FILE = "./valid_words.json"  # List or array of valid dictionary words
OUTPUT_FILE = "./typo_suggestions.json"

MIN_TYPO_FREQUENCY = 2   # Ignore single random key mashing
SIMILARITY_THRESHOLD = 75 # Minimum RapidFuzz match score (0-100)

def normalize_khmer(text: str) -> str:
    """Normalize Khmer Unicode characters to avoid visual duplicate mismatches."""
    return unicodedata.normalize("NFC", text.strip())

def main():
    # 1. Load and aggregate unmatched queries
    print("Parsing unmatched queries...")
    typo_counts = Counter()
    
    with open(UNMATCHED_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            raw_query = data.get("query", "")
            clean_query = normalize_khmer(raw_query)
            
            # Filter out extreme edge cases or single-character noise
            if len(clean_query) > 1:
                typo_counts[clean_query] += 1

    # Filter candidates by occurrence frequency
    frequent_typos = {q: count for q, count in typo_counts.items() if count >= MIN_TYPO_FREQUENCY}
    print(f"Found {len(frequent_typos)} frequent typo candidates (>= {MIN_TYPO_FREQUENCY} occurrences).")

    # 2. Load known valid dictionary words
    print("Loading target vocabulary...")
    with open(VALID_WORDS_FILE, "r", encoding="utf-8") as f:
        # Expects a list of strings: ["កត់ត្រា", "កំណត់ត្រា", ...]
        valid_words = [normalize_khmer(w) for w in json.load(f)]

    # 3. Match typos against valid dictionary using Indel/Levenshtein similarity
    print("Generating matches...")
    suggestions_db = {}

    for typo in frequent_typos:
        # RapidFuzz extract One returns best match: (matched_string, score, index)
        match = process.extractOne(
            typo, 
            valid_words, 
            scorer=fuzz.ratio, 
            score_cutoff=SIMILARITY_THRESHOLD
        )
        
        if match:
            best_match, score, _ = match
            suggestions_db[typo] = {
                "suggestion": best_match,
                "confidence": round(score, 2),
                "occurrences": frequent_typos[typo]
            }

    # 4. Save suggestion mapping
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(suggestions_db, f, ensure_ascii=False, indent=2)

    print(f"Done! Saved {len(suggestions_db)} suggestions to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
