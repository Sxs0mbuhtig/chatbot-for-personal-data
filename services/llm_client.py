"""
services/llm_client.py
~~~~~~~~~~~~~~~~~~~~~~~
GeminiKeyRotator — a thin wrapper around the Google GenAI SDK client that
automatically cycles through a pool of API keys whenever a 429 /
RESOURCE_EXHAUSTED error is encountered.

Configuration
-------------
Set a comma-separated list of keys in the environment (or .env file):

    GEMINI_API_KEYS="key1,key2,key3"

A single-key fallback is also supported via the legacy ``GEMINI_API_KEY``
variable for backward-compatibility.
"""

import os
import time
import math
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _load_keys() -> list[str]:
    """
    Parse GEMINI_API_KEYS (comma-separated) from the environment.
    Falls back to GEMINI_API_KEY for single-key setups.
    """
    pool_raw = os.environ.get("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in pool_raw.split(",") if k.strip()]
    if not keys:
        # Backward-compat: single key
        single = os.environ.get("GEMINI_API_KEY", "").strip()
        if single:
            keys = [single]
    return keys


class GeminiKeyRotator:
    """
    A Google GenAI client wrapper that rotates through a pool of API keys on
    429 / RESOURCE_EXHAUSTED errors.

    Usage
    -----
    ::

        rotator = GeminiKeyRotator()
        response = rotator.generate_content(model="gemini-2.5-flash", **kwargs)

    ``generate_content`` accepts the same keyword arguments as
    ``google.genai.Client.models.generate_content``.  On a 429 error it
    silently advances to the next key and retries.  If every key in the pool
    is exhausted it re-raises the last error.
    """

    def __init__(self, keys: Optional[list[str]] = None, throttle_delay: float = 0.0):
        self._keys: list[str] = keys if keys is not None else _load_keys()
        if not self._keys:
            logger.warning(
                "[GeminiKeyRotator] No API keys found. "
                "Set GEMINI_API_KEYS or GEMINI_API_KEY in your environment."
            )
        self._index: int = 0
        self._clients: dict[str, Any] = {}  # key -> genai.Client, lazily built
        # When > 0, a blocking sleep is injected between key-rotation retries.
        # Intended for batch/telemetry callers (pass throttle_delay=2.0).
        # Leave at 0.0 for latency-sensitive live search requests.
        self.throttle_delay: float = throttle_delay

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_client(self, key: str) -> Any:
        """Return a cached genai.Client for *key*, creating it on first use."""
        if key not in self._clients:
            from google import genai  # import deferred to keep module import fast
            self._clients[key] = genai.Client(api_key=key)
        return self._clients[key]

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        """
        Return True when *exc* signals a 429 / RESOURCE_EXHAUSTED quota error.

        The google-genai SDK raises ``google.genai.errors.APIError`` (or a
        subclass).  We inspect the status code and the gRPC status string so
        the check is resilient to both REST and gRPC transport.
        """
        cls_name = type(exc).__name__
        exc_str = str(exc)

        # SDK-native: google.genai.errors.APIError carries a .code attribute
        code = getattr(exc, "code", None)
        if code == 429:
            return True

        # gRPC / REST status strings
        if "RESOURCE_EXHAUSTED" in exc_str or "429" in exc_str:
            return True

        # Subclass name hints (e.g. ResourceExhausted, TooManyRequests)
        if "ResourceExhausted" in cls_name or "TooManyRequests" in cls_name:
            return True

        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_key(self) -> Optional[str]:
        """The API key that will be used on the next request."""
        if not self._keys:
            return None
        return self._keys[self._index % len(self._keys)]

    def rotate(self) -> None:
        """Advance the key index by one position (wraps around)."""
        if self._keys:
            self._index = (self._index + 1) % len(self._keys)

    def generate_content(self, model: str, **kwargs) -> Any:
        """
        Call ``client.models.generate_content`` with automatic key rotation.

        Parameters
        ----------
        model:
            The Gemini model identifier, e.g. ``"gemini-2.5-flash"``.
        **kwargs:
            Forwarded verbatim to ``genai.Client.models.generate_content``.

        Raises
        ------
        Exception
            Re-raises the last error when all keys in the pool have been
            exhausted without a successful response.
        RuntimeError
            When no API keys are configured at all.
        """
        if not self._keys:
            raise RuntimeError(
                "[GeminiKeyRotator] Cannot call generate_content: no API keys configured."
            )

        last_exc: Optional[Exception] = None
        # Attempt each key at most once per call
        for attempt in range(len(self._keys)):
            key = self._keys[self._index % len(self._keys)]
            try:
                client = self._get_client(key)
                return client.models.generate_content(model=model, **kwargs)
            except Exception as exc:
                if self._is_rate_limit_error(exc):
                    logger.warning(
                        "[GeminiKeyRotator] Key #%d hit rate limit (%s). "
                        "Rotating to next key. (attempt %d/%d)",
                        self._index % len(self._keys),
                        exc,
                        attempt + 1,
                        len(self._keys),
                    )
                    last_exc = exc
                    self.rotate()
                    # Throttle between rotation retries (batch callers only)
                    if self.throttle_delay > 0:
                        time.sleep(self.throttle_delay)
                else:
                    # Non-rate-limit errors are raised immediately
                    raise

        # All keys exhausted
        logger.error(
            "[GeminiKeyRotator] All %d key(s) exhausted. Last error: %s",
            len(self._keys),
            last_exc,
        )
        raise last_exc  # type: ignore[misc]

    def generate_embedding(self, text: str, model: str = "text-embedding-004", dimensions: int = 384) -> list[float]:
        """
        Generate a dense vector embedding for *text* using the Gemini Embedding API.

        The raw model output is typically 768-dimensional.  The result is
        normalized to a unit vector and then truncated or zero-padded to *dimensions*
        so it remains compatible with the Typesense collection schema without
        requiring a schema migration.

        Parameters
        ----------
        text:
            Input string to embed.
        model:
            Gemini embedding model identifier (default ``"text-embedding-004"``).
        dimensions:
            Target output length (default 384 to match Typesense schema).

        Returns
        -------
        list[float]
            Unit-normalized dense vector of length *dimensions*.

        Raises
        ------
        Exception
            Propagates any non-rate-limit SDK error after key rotation is exhausted.
        """
        if not self._keys:
            raise RuntimeError(
                "[GeminiKeyRotator] Cannot call generate_embedding: no API keys configured."
            )

        last_exc: Optional[Exception] = None
        for attempt in range(len(self._keys)):
            key = self._keys[self._index % len(self._keys)]
            try:
                client = self._get_client(key)
                response = client.models.embed_content(
                    model=model,
                    contents=text,
                )
                # Extract the values list from the response
                raw_vec: list[float] = response.embeddings[0].values
                return _normalize_and_resize(raw_vec, dimensions)
            except Exception as exc:
                if self._is_rate_limit_error(exc):
                    logger.warning(
                        "[GeminiKeyRotator] Embedding key #%d hit rate limit. "
                        "Rotating. (attempt %d/%d)",
                        self._index % len(self._keys),
                        attempt + 1,
                        len(self._keys),
                    )
                    last_exc = exc
                    self.rotate()
                    if self.throttle_delay > 0:
                        time.sleep(self.throttle_delay)
                else:
                    raise

        raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helper: resize / normalize embedding vectors
# ---------------------------------------------------------------------------

def _normalize_and_resize(vec: list[float], target_dim: int) -> list[float]:
    """
    Truncate or zero-pad *vec* to *target_dim* and return a unit-normalized copy.
    """
    # Resize
    if len(vec) > target_dim:
        vec = vec[:target_dim]
    elif len(vec) < target_dim:
        vec = vec + [0.0] * (target_dim - len(vec))

    # L2 normalise
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 6) for v in vec]
    return vec


# ---------------------------------------------------------------------------
# Module-level singleton — ready to use across the application.
# ---------------------------------------------------------------------------

gemini_rotator = GeminiKeyRotator()
