import os
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from services.telemetry import telemetry_manager
from services.expressive_engine import expressive_engine
from services.llm_client import GeminiKeyRotator

UNMATCHED_JSON_FILE = "unmatched_queries.json"
UNMATCHED_JSONL_FILE = "unmatched_queries.jsonl"
TELEMETRY_JSON_FILE = "query_telemetry.json"

# =====================================================================
# PYDANTIC SCHEMAS FOR TELEMETRY & BATCH EVALUATION
# =====================================================================

class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    raw_query: str = Field(..., description="Raw query string input from user")
    normalized_root: str = Field(..., description="Normalized root string")
    detected_register: str = Field(default="colloquial_general")
    ip_address: str = Field(default="unknown")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UnmatchedQueryRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    query: str
    normalized_root: str
    detected_register: str
    count: int = 1
    first_logged: str
    last_logged: str
    status: str = "pending_ai_review"

class BatchEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    total_unmatched_unique: int
    evaluated_at: str
    high_priority_candidates: List[UnmatchedQueryRecord]
    register_breakdown: Dict[str, int]

class HistoricalContext(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    boundary_note_km: str = Field(..., description="Historical orthographic or usage boundary note in Khmer")
    educational_explanation_km: str = Field(..., description="Educational explanation in Khmer")
    
class KhmerLinguisticEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    input_term: str = Field(..., description="Raw input query string")
    canonical_headword: str = Field(..., description="Canonical standard headword form")
    norm_root: str = Field(..., description="Normalized root form")
    phonetic_spelling: str = Field(..., description="Khmer phonetic pronunciation spelling")
    pos: str = Field(default="ន.", description="Part of speech tag")
    register_type: str = Field(default="colloquial_general", alias="register", description="Linguistic register category")
    etymology_type: str = Field(default="Colloquial Khmer", description="Etymological origin classification")
    historical_context: HistoricalContext
    definition_km: str = Field(..., description="Khmer language dictionary definition")
    usage_examples: List[str] = Field(default_factory=list, description="Usage example sentences in Khmer")
    phonetic_variants: List[str] = Field(default_factory=list, description="Phonetic spelling variants")
    synonyms: List[str] = Field(default_factory=list, description="Khmer synonyms")
    is_chuon_nath_standard: bool = Field(default=False, description="Whether entry exists in Chuon Nath dictionary")
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0, description="AI confidence score")

    @property
    def register(self) -> str:
        return self.register_type

class LinguisticContext(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    register_type: str = Field(..., alias="register", description="Linguistic register category")
    etymology_type: str = Field(default="native_km")
    boundary_note_km: str = Field(default="")
    educational_explanation_km: str = Field(default="")
    
# =====================================================================
# BATCH TELEMETRY EVALUATOR CLASS
# =====================================================================

class BatchTelemetryEvaluator:
    def __init__(self, storage_dir: str = "."):
        self.storage_dir = storage_dir
        self.unmatched_json_path = os.path.join(storage_dir, UNMATCHED_JSON_FILE)
        self.unmatched_jsonl_path = os.path.join(storage_dir, UNMATCHED_JSONL_FILE)
        self.telemetry_json_path = os.path.join(storage_dir, TELEMETRY_JSON_FILE)

    def _load_json(self, path: str) -> Dict[str, Any]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_json(self, path: str, data: Dict[str, Any]):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def queue_unmatched_query(
        self,
        raw_query: str,
        normalized_root: str,
        detected_register: str,
        ip: str = "unknown"
    ) -> TelemetryPayload:
        """
        Validates payload via Pydantic and logs unmatched query telemetry to JSON/JSONL queues.
        """
        payload = TelemetryPayload(
            raw_query=raw_query,
            normalized_root=normalized_root,
            detected_register=detected_register,
            ip_address=ip
        )

        unmatched = self._load_json(self.unmatched_json_path)
        q_key = payload.normalized_root or payload.raw_query

        if q_key not in unmatched:
            unmatched[q_key] = {
                "query": payload.raw_query,
                "normalized_root": payload.normalized_root,
                "detected_register": payload.detected_register,
                "count": 0,
                "first_logged": payload.timestamp,
                "last_logged": payload.timestamp,
                "status": "pending_ai_review"
            }

        unmatched[q_key]["count"] += 1
        unmatched[q_key]["last_logged"] = payload.timestamp
        unmatched[q_key]["detected_register"] = payload.detected_register
        self._save_json(self.unmatched_json_path, unmatched)

        try:
            with open(self.unmatched_jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload.model_dump(), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[BatchEvaluator Warning] Failed writing jsonl: {e}")

        return payload

    def evaluate_batch(self, min_hits: int = 1) -> BatchEvaluationReport:
        """
        Aggregates unmatched telemetry, generates candidate list for AI ingestion,
        and provides register metrics.
        """
        unmatched_data = self._load_json(self.unmatched_json_path)
        candidates: List[UnmatchedQueryRecord] = []
        register_counts: Dict[str, int] = {}

        for item in unmatched_data.values():
            rec = UnmatchedQueryRecord(
                query=item.get("query", ""),
                normalized_root=item.get("normalized_root", item.get("query", "")),
                detected_register=item.get("detected_register", "colloquial_general"),
                count=item.get("count", 1),
                first_logged=item.get("first_logged", datetime.now(timezone.utc).isoformat()),
                last_logged=item.get("last_logged", datetime.now(timezone.utc).isoformat()),
                status=item.get("status", "pending_ai_review")
            )
            
            reg = rec.detected_register
            register_counts[reg] = register_counts.get(reg, 0) + rec.count

            if rec.count >= min_hits:
                candidates.append(rec)

        candidates.sort(key=lambda x: x.count, reverse=True)

        return BatchEvaluationReport(
            total_unmatched_unique=len(unmatched_data),
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            high_priority_candidates=candidates,
            register_breakdown=register_counts
        )

# =====================================================================
# LLM BATCH CURATOR SERVICE
# =====================================================================

class LLMBatchCurator:
    def __init__(self, rotator: Optional[GeminiKeyRotator] = None):
        # Accept an injected rotator (useful for testing) or create a default one.
        self.rotator: GeminiKeyRotator = rotator if rotator is not None else GeminiKeyRotator()

    async def evaluate_batch(self, min_hits: int = 5, max_batch_size: int = 5, sleep_interval: float = 2.0) -> List[KhmerLinguisticEntry]:
        """
        Fetches candidates from TelemetryManager meeting min_hits and generates structured
        Pydantic KhmerLinguisticEntry entries via Google GenAI or deterministic fallback.
        Includes asynchronous rate-limiting and max 5 queries per batch call to prevent API quota lockouts.
        """
        import asyncio
        top_queries = await telemetry_manager.get_top_unresolved_queries(limit=100)
        candidates = [q for q in top_queries if q.get("hits", 0) >= min_hits][:max_batch_size]

        results: List[KhmerLinguisticEntry] = []
        for idx, cand in enumerate(candidates):
            if idx > 0 and sleep_interval > 0:
                await asyncio.sleep(sleep_interval)
            term = cand.get("term") or cand.get("raw_query")
            reg_meta = cand.get("register_meta", {})
            entry = await self._curate_single_term(term, reg_meta)
            if entry:
                results.append(entry)
        return results

    async def _curate_single_term(
        self,
        term: str,
        reg_meta: Dict[str, Any],
        max_retries: int = 3,
        base_backoff: float = 2.0
    ) -> Optional[KhmerLinguisticEntry]:
        import asyncio
        if self.rotator.current_key:
            for attempt in range(max_retries):
                try:
                    prompt = f"""
                    You are a Senior Khmer Computational Linguist and Lexicographer.
                    Analyze the unrecognized Khmer search query term '{term}'.
                    Contextual Register hints: {json.dumps(reg_meta, ensure_ascii=False)}
                    
                    Produce a structured linguistic definition dictionary entry in Khmer.
                    """
                    response = self.rotator.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": KhmerLinguisticEntry,
                        }
                    )
                    if response and getattr(response, "parsed", None):
                        return response.parsed
                except Exception as e:
                    err_msg = str(e).lower()
                    status_code = getattr(e, "code", getattr(e, "status_code", None))
                    if status_code == 429 or "429" in err_msg or "resource_exhausted" in err_msg or "quota" in err_msg:
                        backoff = base_backoff * (2 ** attempt)
                        print(f"[LLMBatchCurator 429 Quota Exceeded] Backing off for {backoff}s (attempt {attempt + 1}/{max_retries})...")
                        await asyncio.sleep(backoff)
                        self.rotator.rotate_key()
                    else:
                        print(f"[LLMBatchCurator Gemini Error] for term '{term}': {e}")
                        break

        # Deterministic Fallback Generator for test/offline environments
        digestion = expressive_engine.digest_input(term)
        ling_context = digestion.linguistic_context
        
        hist_context = HistoricalContext(
            boundary_note_km=ling_context.boundary_note_km,
            educational_explanation_km=ling_context.educational_explanation_km
        )

        return KhmerLinguisticEntry(
            input_term=term,
            canonical_headword=digestion.normalized_root,
            norm_root=digestion.normalized_root,
            phonetic_spelling=term,
            pos="ន." if "loanword" in ling_context.register else "កិ.គុ.",
            register=ling_context.register,
            etymology_type=ling_context.etymology_type,
            historical_context=hist_context,
            definition_km=f"ពាក្យ «{term}» ត្រូវបានវិភាគដោយប្រព័ន្ធ AI ស្វ័យប្រវត្តិ។",
            usage_examples=[f"ការប្រើប្រាស់ពាក្យ {term} ក្នុងល្បះគំរូ។"],
            phonetic_variants=digestion.phonetic_variants,
            synonyms=[],
            is_chuon_nath_standard=ling_context.register == "formal_classical",
            confidence_score=0.9
        )

# Global singletons
batch_evaluator = BatchTelemetryEvaluator()
llm_batch_curator = LLMBatchCurator()
