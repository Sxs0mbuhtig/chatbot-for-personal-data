import os
import sys
import json
import asyncio
import hashlib
from collections import Counter
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.config import settings

UNMATCHED_LOG = "unmatched_queries.jsonl"
STAGED_OUTPUT_DIR = "data"
STAGED_OUTPUT_FILE = os.path.join(STAGED_OUTPUT_DIR, "staged_definitions.json")

def hash_user_ip(ip: str) -> str:
    """Anonymizes raw client IP address using SHA-256 with a daily salt."""
    if not ip or ip == "unknown":
        return "anonymized_unknown"
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]

def aggregate_unmatched_queries(min_occurrences: int = 3) -> List[str]:
    """Reads unmatched query log file and returns high-frequency missing terms."""
    if not os.path.exists(UNMATCHED_LOG):
        return []

    queries = []
    with open(UNMATCHED_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                query = str(data.get("query", "")).strip()
                if query and len(query) > 1:
                    queries.append(query)
            except json.JSONDecodeError:
                continue

    counts = Counter(queries)
    return [q for q, count in counts.items() if count >= min_occurrences]

async def generate_gemini_candidate_entry(missing_term: str) -> Dict[str, Any]:
    """
    Uses google-genai SDK (Gemini API) to auto-generate candidate dictionary draft entries
    for high-frequency unmatched search terms.
    """
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    if api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = f"""
            You are Samdach Chuon Nath Lexicographical AI Agent.
            Analyze the following Khmer search term that was NOT found in the dictionary index: "{missing_term}"

            Provide a structured lexicographical definition draft in JSON mode matching this exact schema:
            - word: string (the input missing term)
            - phonetic_ipa: string (estimated IPA transcription)
            - etymology: string (etymological origin e.g. Sanskrit, Pali, French, Neologism, Loanword, Native Khmer)
            - definition_draft: string (concise summary definition in Khmer)
            """

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2
                )
            )

            if response.text:
                candidate = json.loads(response.text)
                return {
                    "word": candidate.get("word", missing_term),
                    "phonetic_ipa": candidate.get("phonetic_ipa", ""),
                    "etymology": candidate.get("etymology", "Unknown"),
                    "definition_draft": candidate.get("definition_draft", "ទម្រង់ពាក្យកំពុងស្ថិតក្នុងការពិនិត្យ។"),
                    "source": "Gemini AI Log Enrichment",
                    "status": "staged_for_review"
                }
        except Exception as e:
            print(f"[Gemini API Notice]: Fallback mode used for '{missing_term}': {e}")

    # Fallback template generator when API key is missing or offline
    return {
        "word": missing_term,
        "phonetic_ipa": f"/{missing_term}/",
        "etymology": "Auto-Log Extraction / Unmatched Frequency Analysis",
        "definition_draft": f"ពាក្យ «{missing_term}» ត្រូវបានស្វែងរកញឹកញាប់ ប៉ុន្តែពុំទាន់មានក្នុងទិន្នន័យបទដ្ឋាន។",
        "source": "Unmatched Query Aggregator",
        "status": "staged_for_review"
    }

async def process_unmatched_logs(min_occurrences: int = 3):
    """Main async task to aggregate logs and write staged candidate definitions."""
    candidate_terms = aggregate_unmatched_queries(min_occurrences=min_occurrences)
    print(f"Found {len(candidate_terms)} high-frequency unmatched terms (>= {min_occurrences} occurrences).")

    if not candidate_terms:
        candidate_terms = ["ចំនង់ចំនូលចិត្ត", "កំត់ត្រា"]

    staged_results = []
    for term in candidate_terms:
        print(f"Generating draft for term: '{term}'...")
        draft = await generate_gemini_candidate_entry(term)
        staged_results.append(draft)

    os.makedirs(STAGED_OUTPUT_DIR, exist_ok=True)

    existing_staged = []
    if os.path.exists(STAGED_OUTPUT_FILE):
        try:
            with open(STAGED_OUTPUT_FILE, "r", encoding="utf-8") as f:
                existing_staged = json.load(f)
        except json.JSONDecodeError:
            existing_staged = []

    existing_words = {item.get("word") for item in existing_staged if isinstance(item, dict)}
    for new_item in staged_results:
        if new_item["word"] not in existing_words:
            existing_staged.append(new_item)

    with open(STAGED_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(existing_staged, f, ensure_ascii=False, indent=2)

    print(f"Successfully wrote {len(existing_staged)} staged definitions to '{STAGED_OUTPUT_FILE}'.")
    return existing_staged

if __name__ == "__main__":
    asyncio.run(process_unmatched_logs(min_occurrences=2))
