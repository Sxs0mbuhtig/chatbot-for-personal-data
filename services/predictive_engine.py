import re
import sqlite3
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from khmer_normalizer import (
    clean_khmer_text,
    count_khmer_graphemes,
    get_independent_vowel_variants
)
from services.expressive_engine import expressive_engine, ALTERNATION_SETS

DB_PATH = "chuon_nath_fts.db"

class CandidateSuggestion(BaseModel):
    model_config = ConfigDict(extra="ignore", protected_namespaces=())
    candidate: str = Field(..., description="Suggested candidate word or phrase")
    score: float = Field(..., description="Relevance / similarity score")
    match_type: str = Field(..., description="prefix, edit_distance, or phonetic_variant")


class KhmerPredictiveEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def _query_prefix_matches(self, root: str, limit: int = 15) -> List[str]:
        if not os.path.exists(self.db_path) or not root:
            return []
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            cursor = conn.cursor()
            pattern = f"{root}%"
            cursor.execute(
                """
                SELECT headword FROM dictionary
                WHERE headword LIKE ? OR norm_headword LIKE ?
                ORDER BY LENGTH(headword) ASC
                LIMIT ?
                """,
                (pattern, pattern, limit)
            )
            rows = cursor.fetchall()
            return [r[0] for r in rows]
        except Exception:
            return []
        finally:
            if conn:
                conn.close()

    def _grapheme_levenshtein(self, s1: str, s2: str) -> int:
        """Computes Levenshtein edit distance over Khmer visual graphemes."""
        # Split s1 and s2 into grapheme clusters
        pattern = r"\u17d7|[\u1780-\u17b3][\u17c9\u17ca]?(?:\u17d2[\u1780-\u17b3])*(?:[\u17b6-\u17c5])*(?:[\u17c6-\u17d3])*|[^\u1780-\u17b3]"
        g1 = [c for c in re.findall(pattern, s1) if c.strip()]
        g2 = [c for c in re.findall(pattern, s2) if c.strip()]

        m, n = len(g1), len(g2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if g1[i - 1] == g2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
        return dp[m][n]

    def generate_suggestions(self, query: str, max_candidates: int = 10) -> List[CandidateSuggestion]:
        clean = clean_khmer_text(query)
        if not clean:
            return []

        candidates_map: Dict[str, CandidateSuggestion] = {}

        # 1. Phonetic variant expansion (L/R/ឡ, shifters ៉/៊, independent vowels)
        phonetic_vars = expressive_engine.generate_phonetic_variants(clean, max_variants=10)
        for var in phonetic_vars:
            if var != clean and var not in candidates_map:
                candidates_map[var] = CandidateSuggestion(
                    candidate=var,
                    score=0.9,
                    match_type="phonetic_variant"
                )

        # 2. Prefix matching on canonical normalized roots
        prefix_matches = self._query_prefix_matches(clean, limit=15)
        for pm in prefix_matches:
            if pm not in candidates_map:
                candidates_map[pm] = CandidateSuggestion(
                    candidate=pm,
                    score=1.0 if pm == clean else 0.85,
                    match_type="prefix"
                )

        # 3. Grapheme cluster edit distance evaluation (if candidates are few)
        if len(candidates_map) < max_candidates:
            # Query dictionary terms with similar length or starting character to find edit distance neighbors
            first_char = clean[0] if clean else ""
            prefix_broad = self._query_prefix_matches(first_char, limit=30)
            for bm in prefix_broad:
                if bm not in candidates_map:
                    dist = self._grapheme_levenshtein(clean, bm)
                    if dist <= 2:
                        score = max(0.1, 0.8 - (dist * 0.2))
                        candidates_map[bm] = CandidateSuggestion(
                            candidate=bm,
                            score=score,
                            match_type="edit_distance"
                        )

        # Sort candidates by score descending and return top max_candidates
        sorted_candidates = sorted(candidates_map.values(), key=lambda c: c.score, reverse=True)
        return sorted_candidates[:max_candidates]


predictive_engine = KhmerPredictiveEngine()
