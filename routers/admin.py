import time
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field

from services.telemetry import telemetry_manager
from services.batch_evaluator import llm_batch_curator, KhmerLinguisticEntry
from services.expressive_engine import build_typesense_payload, expressive_engine
from services.lexicon import ts_client, COLLECTION_NAME

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Pipeline"])

class CurationResponse(BaseModel):
    status: str
    min_hits: int
    auto_index: bool
    processed_count: int
    indexed_count: int
    curated_entries: List[KhmerLinguisticEntry]
    errors: List[str] = Field(default_factory=list)

@router.get("/telemetry/top", response_model=List[Dict[str, Any]])
async def get_top_unresolved_telemetry(
    limit: int = Query(default=50, ge=1, le=500)
):
    """
    Retrieves top N unresolved search queries sorted by hit frequency from Redis/Telemetry store.
    """
    try:
        top_items = await telemetry_manager.get_top_unresolved_queries(limit=limit)
        return top_items
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed retrieving unresolved telemetry: {str(e)}"
        )

@router.post("/curate-telemetry", response_model=CurationResponse)
async def curate_telemetry_batch(
    min_hits: int = Query(default=5, ge=1),
    auto_index: bool = Query(default=False)
):
    """
    Triggers LLM Batch Curator for high-frequency unresolved search queries, validates schema,
    optionally upserts documents to Typesense, and clears processed terms from telemetry queue.
    """
    errors: List[str] = []
    indexed_count = 0

    try:
        curated_entries = await llm_batch_curator.evaluate_batch(min_hits=min_hits)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch evaluation failed: {str(e)}"
        )

    processed_terms = []
    for entry in curated_entries:
        processed_terms.append(entry.norm_root)
        if auto_index:
            try:
                # Build searchable Typesense document payload
                ts_doc = {
                    "headword": entry.input_term,
                    "norm_headword": entry.norm_root,
                    "canonical_headword": entry.canonical_headword,
                    "pos": entry.pos,
                    "register": entry.register,
                    "definition": entry.definition_km,
                    "synonyms": entry.synonyms,
                    "phonetic_variants": entry.phonetic_variants,
                    "is_official_chuon_nath": entry.is_chuon_nath_standard,
                    "source_title": "AI Automated Curation Engine",
                    "sort_index": int(time.time())
                }
                payload = build_typesense_payload(ts_doc, expressive_engine)
                ts_client.collections[COLLECTION_NAME].documents.upsert(payload)
                indexed_count += 1
            except Exception as e:
                err_msg = f"Failed indexing '{entry.norm_root}' into Typesense: {e}"
                print(f"[Admin Curation Notice] {err_msg}")
                errors.append(err_msg)

    # Clear processed terms from Telemetry queue
    if processed_terms:
        await telemetry_manager.clear_processed_queries(processed_terms)

    return CurationResponse(
        status="success",
        min_hits=min_hits,
        auto_index=auto_index,
        processed_count=len(curated_entries),
        indexed_count=indexed_count,
        curated_entries=curated_entries,
        errors=errors
    )
