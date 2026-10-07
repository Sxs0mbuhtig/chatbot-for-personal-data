import json
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:14b"

# Optional Cloud API Endpoint (e.g., OpenRouter, Gemini, or custom proxy)
API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = "YOUR_API_KEY_HERE"  # Keep in environment variable in production

SYSTEM_PROMPT = """You are an expert Khmer etymologist. 
Analyze Khmer compound words derived from Pali or Sanskrit. 
Return ONLY a JSON object with keys: "root_1", "root_2", and "meaning".
Roots must strictly use Khmer script characters only (e.g., នយ + ឧបាយ -> នយោបាយ). Never use Devanagari or Latin characters for roots."""

def query_ollama(khmer_word):
    prompt = f"Word: {khmer_word}\nProvide the exact root components and English meaning in JSON."
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "format": "json",
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=90)
        res_json = response.json()
        return json.loads(res_json.get("response", "{}"))
    except Exception as e:
        print(f"[Ollama Error]: {e}")
        return None

def query_cloud_api(khmer_word):
    """Fallback API call for complex etymologies."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat", # or google/gemini-flash / anthropic/claude-3.5-haiku
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze word: {khmer_word}"}
        ],
        "response_format": {"type": "json_object"}
    }
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        print(f"[API Error]: {e}")
        return None

def validate_parse(result, word):
    """Quality check to ensure local LLM didn't hallucinate or fail."""
    if not result or not isinstance(result, dict):
        return False
    
    root1 = result.get("root_1", "")
    root2 = result.get("root_2", "")
    meaning = result.get("meaning", "")

    if not root1 or not root2 or not meaning:
        return False

    # Known failure pattern: splitting 'នយោបាយ' into literal 'បាយ' (cooked rice)
    if word == "នយោបាយ" and root2 == "បាយ":
        return False

    return True

def parse_khmer_lexicon(word):
    print(f"--- Processing: {word} ---")
    
    # Try Local Ollama 7B first
    result = query_ollama(word)
    
    if validate_parse(result, word):
        print(f"✓ Resolved via Local Ollama ({OLLAMA_MODEL})")
        return result
    
    # Fallback to API if local validation fails or key is present
    print("⚠ Local validation failed or low-confidence result. Triggering API Fallback...")
    if API_KEY and API_KEY != "YOUR_API_KEY_HERE":
        api_result = query_cloud_api(word)
        if api_result:
            print("✓ Resolved via Cloud API Fallback")
            return api_result
            
    print("X Parse failed on both local and cloud endpoints.")
    return result

# --- Execution Test ---
if __name__ == "__main__":
    test_word = "នយោបាយ"
    output = parse_khmer_lexicon(test_word)
    print(json.dumps(output, indent=2, ensure_ascii=False))
