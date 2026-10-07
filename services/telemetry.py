import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    try:
        import redis as aioredis
        HAS_REDIS = True
    except ImportError:
        aioredis = None
        HAS_REDIS = False


logger = logging.getLogger(__name__)

# =====================================================================
# PYDANTIC METADATA SCHEMA
# =====================================================================

class UnresolvedQueryMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")
    raw_query: str
    normalized_root: str
    register_meta: Dict[str, Any] = Field(default_factory=dict)
    first_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

# =====================================================================
# TELEMETRY MANAGER CLASS
# =====================================================================

class TelemetryManager:
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        use_in_memory_fallback: bool = True
    ):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.use_in_memory_fallback = use_in_memory_fallback

        self._redis_client: Optional[Any] = None
        self._memory_hits: Dict[str, int] = {}
        self._memory_meta: Dict[str, Dict[str, Any]] = {}

    async def get_redis_client(self) -> Optional[Any]:
        """Lazy initialization of async Redis client with connection error fallback."""
        if not HAS_REDIS or aioredis is None:
            return None

        if self._redis_client is not None:
            return self._redis_client


        try:
            client = aioredis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_timeout=1.0,
                socket_connect_timeout=1.0
            )
            # Test connection
            await client.ping()
            self._redis_client = client
            return self._redis_client
        except Exception as e:
            logger.warning(f"[TelemetryManager Redis Notice]: Could not connect to Redis at {self.redis_host}:{self.redis_port}. Degrading to in-memory fallback store. Error: {e}")
            self._redis_client = None
            return None

    async def record_unresolved_query(
        self,
        raw_query: str,
        normalized_root: str,
        register_meta: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Asynchronously records zero-hit/unresolved query telemetry to Redis or in-memory fallback.
        Increments ZSET counter 'lexicon:unresolved_hits' and updates HSET 'lexicon:unresolved_meta:<root>'.
        """
        root_key = normalized_root or raw_query
        reg_meta = register_meta or {}
        now_iso = datetime.now(timezone.utc).isoformat()

        client = await self.get_redis_client()

        if client is not None:
            try:
                # 1. Increment hit counter in Sorted Set
                await client.zincrby("lexicon:unresolved_hits", 1, root_key)

                # 2. Store or update metadata Hash
                meta_key = f"lexicon:unresolved_meta:{root_key}"
                existing = await client.hgetall(meta_key)
                
                if existing:
                    await client.hset(meta_key, "last_seen", now_iso)
                    await client.hset(meta_key, "count", int(existing.get("count", 1)) + 1)
                else:
                    payload = {
                        "raw_query": raw_query,
                        "normalized_root": root_key,
                        "register_meta": json.dumps(reg_meta, ensure_ascii=False),
                        "first_seen": now_iso,
                        "last_seen": now_iso,
                        "count": 1
                    }
                    await client.hset(meta_key, mapping=payload)
                return
            except Exception as e:
                logger.warning(f"[TelemetryManager Redis Recording Exception]: {e}. Falling back to in-memory store.")

        # In-Memory Fallback Implementation
        self._memory_hits[root_key] = self._memory_hits.get(root_key, 0) + 1
        if root_key not in self._memory_meta:
            self._memory_meta[root_key] = {
                "raw_query": raw_query,
                "normalized_root": root_key,
                "register_meta": reg_meta,
                "first_seen": now_iso,
                "last_seen": now_iso
            }
        else:
            self._memory_meta[root_key]["last_seen"] = now_iso

    async def get_top_unresolved_queries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Returns top N unresolved search terms sorted by hit frequency.
        """
        client = await self.get_redis_client()

        if client is not None:
            try:
                # Fetch top N terms with scores from ZSET
                top_items = await client.zrevrange("lexicon:unresolved_hits", 0, limit - 1, withscores=True)
                results = []
                for term, hits in top_items:
                    meta_key = f"lexicon:unresolved_meta:{term}"
                    raw_meta = await client.hgetall(meta_key)
                    reg_meta_parsed = {}
                    if raw_meta.get("register_meta"):
                        try:
                            reg_meta_parsed = json.loads(raw_meta["register_meta"])
                        except Exception:
                            reg_meta_parsed = {}

                    results.append({
                        "term": term,
                        "normalized_root": term,
                        "raw_query": raw_meta.get("raw_query", term),
                        "hits": int(hits),
                        "register_meta": reg_meta_parsed,
                        "first_seen": raw_meta.get("first_seen"),
                        "last_seen": raw_meta.get("last_seen")
                    })
                return results
            except Exception as e:
                logger.warning(f"[TelemetryManager Redis Fetch Exception]: {e}. Reading from in-memory fallback.")

        # In-Memory Fallback Sort & Fetch
        sorted_terms = sorted(self._memory_hits.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for term, hits in sorted_terms:
            meta = self._memory_meta.get(term, {})
            results.append({
                "term": term,
                "normalized_root": term,
                "raw_query": meta.get("raw_query", term),
                "hits": hits,
                "register_meta": meta.get("register_meta", {}),
                "first_seen": meta.get("first_seen"),
                "last_seen": meta.get("last_seen")
            })
        return results

    async def clear_processed_queries(self, terms: List[str]) -> None:
        """
        Removes evaluated terms from Redis sorted set and metadata store.
        """
        if not terms:
            return

        client = await self.get_redis_client()

        if client is not None:
            try:
                for term in terms:
                    await client.zrem("lexicon:unresolved_hits", term)
                    await client.delete(f"lexicon:unresolved_meta:{term}")
                return
            except Exception as e:
                logger.warning(f"[TelemetryManager Redis Clear Exception]: {e}")

        # In-Memory Clear
        for term in terms:
            self._memory_hits.pop(term, None)
            self._memory_meta.pop(term, None)

    async def run_curation_batch(
        self,
        min_hits: int = 5,
        throttle_seconds: float = 2.0,
        limit: int = 100,
    ) -> list:
        """
        Process the top unresolved queries through the LLM batch curator, with a
        configurable throttle sleep between consecutive LLM calls to protect the
        Gemini API key pool from rate-limit exhaustion during bulk runs.

        Parameters
        ----------
        min_hits:
            Minimum hit count a term must have to be submitted for curation.
        throttle_seconds:
            Seconds to ``asyncio.sleep`` between successive LLM curation calls.
            Defaults to 2.0 as required by the Phase 3 architectural spec.
        limit:
            Maximum number of unresolved terms to fetch from the store.

        Returns
        -------
        list
            A list of ``KhmerLinguisticEntry`` objects (or ``None`` entries for
            terms that the LLM could not process).
        """
        # Deferred import to avoid circular dependency:
        # batch_evaluator -> telemetry_manager -> batch_evaluator
        from services.batch_evaluator import llm_batch_curator

        top_queries = await self.get_top_unresolved_queries(limit=limit)
        candidates = [q for q in top_queries if q.get("hits", 0) >= min_hits]

        curated: list = []
        for idx, cand in enumerate(candidates):
            term = cand.get("term") or cand.get("raw_query", "")
            reg_meta = cand.get("register_meta", {})

            entry = await llm_batch_curator._curate_single_term(term, reg_meta)
            curated.append(entry)

            # Sleep between calls (skip after the very last item to avoid
            # an unnecessary delay at the end of the batch).
            if idx < len(candidates) - 1 and throttle_seconds > 0:
                await asyncio.sleep(throttle_seconds)

        return curated



# Singleton Instance
telemetry_manager = TelemetryManager()
