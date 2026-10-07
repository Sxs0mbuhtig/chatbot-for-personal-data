import os
import json
import hashlib
from datetime import datetime, timezone

TELEMETRY_FILE = "query_telemetry.json"
UNMATCHED_FILE = "unmatched_queries.json"

def hash_user_ip(ip: str) -> str:
    """Hashes IP address for GDPR/privacy compliance."""
    if not ip or ip == "unknown":
        return "anonymized_unknown"
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]

def _load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def log_query(query: str, ip: str, status: str = "exact_match", hits: int = 1):
    data = _load_json(TELEMETRY_FILE)
    hashed_ip = hash_user_ip(ip)
    if query not in data:
        data[query] = {
            "count": 0,
            "status": status,
            "last_searched": None,
            "ips": []
        }
    
    data[query]["count"] += 1
    data[query]["status"] = status
    data[query]["last_searched"] = datetime.now(timezone.utc).isoformat()
    if hashed_ip not in data[query]["ips"]:
        data[query]["ips"].append(hashed_ip)

    _save_json(TELEMETRY_FILE, data)

def log_unmatched_query(query: str, ip: str):
    log_query(query, ip, status="unmatched_queued", hits=0)
    
    unmatched = _load_json(UNMATCHED_FILE)
    if query not in unmatched:
        unmatched[query] = {
            "query": query,
            "count": 0,
            "first_logged": datetime.now(timezone.utc).isoformat(),
            "last_logged": None,
            "status": "pending_ai_review"
        }
    
    unmatched[query]["count"] += 1
    unmatched[query]["last_logged"] = datetime.now(timezone.utc).isoformat()
    _save_json(UNMATCHED_FILE, unmatched)

