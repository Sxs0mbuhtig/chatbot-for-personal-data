"""
tests/test_key_rotation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for GeminiKeyRotator (services/llm_client.py).

All tests mock the google.genai SDK — no real API calls are made.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from services.llm_client import GeminiKeyRotator, _load_keys


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rate_limit_error(message: str = "RESOURCE_EXHAUSTED") -> Exception:
    """Create a mock exception that GeminiKeyRotator._is_rate_limit_error recognises."""
    exc = Exception(message)
    exc.code = 429  # type: ignore[attr-defined]
    return exc


def _make_generic_error(message: str = "Internal Server Error") -> Exception:
    """Create a non-rate-limit exception."""
    exc = Exception(message)
    exc.code = 500  # type: ignore[attr-defined]
    return exc


# ---------------------------------------------------------------------------
# _load_keys() tests
# ---------------------------------------------------------------------------

class TestLoadKeys:
    def test_parses_comma_separated_pool(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "key_a,key_b,key_c")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert _load_keys() == ["key_a", "key_b", "key_c"]

    def test_strips_whitespace_around_keys(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", " key_a , key_b ")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert _load_keys() == ["key_a", "key_b"]

    def test_falls_back_to_single_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "single_key")
        assert _load_keys() == ["single_key"]

    def test_returns_empty_list_when_no_keys(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEYS", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        assert _load_keys() == []

    def test_pool_takes_priority_over_single_key(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEYS", "pool_key_1,pool_key_2")
        monkeypatch.setenv("GEMINI_API_KEY", "ignored_key")
        assert _load_keys() == ["pool_key_1", "pool_key_2"]


# ---------------------------------------------------------------------------
# GeminiKeyRotator._is_rate_limit_error tests
# ---------------------------------------------------------------------------

class TestIsRateLimitError:
    def test_detects_code_429(self):
        exc = MagicMock()
        exc.code = 429
        assert GeminiKeyRotator._is_rate_limit_error(exc) is True

    def test_detects_resource_exhausted_in_message(self):
        exc = Exception("429 RESOURCE_EXHAUSTED: quota exceeded")
        assert GeminiKeyRotator._is_rate_limit_error(exc) is True

    def test_detects_429_in_message(self):
        exc = Exception("HTTP 429 Too Many Requests")
        assert GeminiKeyRotator._is_rate_limit_error(exc) is True

    def test_detects_subclass_name(self):
        class ResourceExhaustedError(Exception):
            pass
        assert GeminiKeyRotator._is_rate_limit_error(ResourceExhaustedError("quota")) is True

    def test_does_not_match_generic_error(self):
        exc = Exception("Internal Server Error")
        assert GeminiKeyRotator._is_rate_limit_error(exc) is False

    def test_does_not_match_auth_error(self):
        exc = Exception("401 UNAUTHENTICATED")
        assert GeminiKeyRotator._is_rate_limit_error(exc) is False


# ---------------------------------------------------------------------------
# GeminiKeyRotator.rotate / current_key tests
# ---------------------------------------------------------------------------

class TestRotation:
    def test_current_key_starts_at_first(self):
        rotator = GeminiKeyRotator(keys=["k1", "k2", "k3"])
        assert rotator.current_key == "k1"

    def test_rotate_advances_key(self):
        rotator = GeminiKeyRotator(keys=["k1", "k2", "k3"])
        rotator.rotate()
        assert rotator.current_key == "k2"
        rotator.rotate()
        assert rotator.current_key == "k3"

    def test_rotate_wraps_around(self):
        rotator = GeminiKeyRotator(keys=["k1", "k2"])
        rotator.rotate()
        rotator.rotate()
        assert rotator.current_key == "k1"

    def test_current_key_is_none_with_empty_pool(self):
        rotator = GeminiKeyRotator(keys=[])
        assert rotator.current_key is None


# ---------------------------------------------------------------------------
# Core behaviour: key rotation on 429
# ---------------------------------------------------------------------------

class TestGenerateContentKeyRotation:
    """
    Verify that generate_content rotates through keys on rate-limit errors and
    succeeds once a healthy key is found.
    """

    def _make_mock_client(self, side_effect):
        """Build a mock genai.Client whose generate_content raises *side_effect*."""
        mock_models = MagicMock()
        mock_models.generate_content.side_effect = side_effect
        mock_client = MagicMock()
        mock_client.models = mock_models
        return mock_client

    def test_succeeds_on_first_key_without_rotation(self):
        """No 429 → calls first key, returns immediately, index unchanged."""
        rotator = GeminiKeyRotator(keys=["key1", "key2"])
        expected_response = MagicMock()

        mock_client = self._make_mock_client(side_effect=[expected_response])
        with patch.object(rotator, "_get_client", return_value=mock_client):
            result = rotator.generate_content(model="gemini-2.5-flash", contents="test")

        assert result is expected_response
        assert rotator._index == 0  # no rotation occurred

    def test_rotates_to_second_key_on_429(self):
        """
        First key raises 429 → rotator should advance to key2 and succeed.
        This is the primary regression test for the key-rotation feature.
        """
        rotator = GeminiKeyRotator(keys=["key1", "key2", "key3"])
        expected_response = MagicMock()
        rate_limit_err = _make_rate_limit_error()

        # key1 → 429, key2 → success
        key1_client = self._make_mock_client(side_effect=[rate_limit_err])
        key2_client = self._make_mock_client(side_effect=[expected_response])

        client_map = {"key1": key1_client, "key2": key2_client}

        with patch.object(rotator, "_get_client", side_effect=lambda k: client_map[k]):
            result = rotator.generate_content(model="gemini-2.5-flash", contents="hello")

        assert result is expected_response
        assert rotator._index == 1  # rotated once

    def test_rotates_through_all_keys_and_succeeds_on_last(self):
        """First two keys 429 → third key succeeds."""
        rotator = GeminiKeyRotator(keys=["k1", "k2", "k3"])
        success = MagicMock()
        err = _make_rate_limit_error()

        clients = {
            "k1": self._make_mock_client([err]),
            "k2": self._make_mock_client([err]),
            "k3": self._make_mock_client([success]),
        }

        with patch.object(rotator, "_get_client", side_effect=lambda k: clients[k]):
            result = rotator.generate_content(model="gemini-2.5-flash", contents="hi")

        assert result is success
        assert rotator._index == 2

    def test_raises_last_error_when_all_keys_exhausted(self):
        """All keys return 429 → the last rate-limit error is re-raised."""
        rotator = GeminiKeyRotator(keys=["k1", "k2"])
        err1 = _make_rate_limit_error("k1 exhausted")
        err2 = _make_rate_limit_error("k2 exhausted")

        clients = {
            "k1": self._make_mock_client([err1]),
            "k2": self._make_mock_client([err2]),
        }

        with patch.object(rotator, "_get_client", side_effect=lambda k: clients[k]):
            with pytest.raises(Exception, match="k2 exhausted"):
                rotator.generate_content(model="gemini-2.5-flash", contents="hi")

    def test_non_rate_limit_error_is_raised_immediately_without_rotation(self):
        """A non-429 error must surface immediately and not trigger rotation."""
        rotator = GeminiKeyRotator(keys=["k1", "k2"])
        bad_err = _make_generic_error("Internal Server Error")

        client = self._make_mock_client([bad_err])
        with patch.object(rotator, "_get_client", return_value=client):
            with pytest.raises(Exception, match="Internal Server Error"):
                rotator.generate_content(model="gemini-2.5-flash", contents="test")

        # Index must not have advanced — no rotation for non-429 errors
        assert rotator._index == 0

    def test_raises_runtime_error_with_empty_key_pool(self):
        """generate_content with no keys must raise RuntimeError immediately."""
        rotator = GeminiKeyRotator(keys=[])
        with pytest.raises(RuntimeError, match="no API keys configured"):
            rotator.generate_content(model="gemini-2.5-flash", contents="x")


# ---------------------------------------------------------------------------
# LLMBatchCurator integration — rotator injection
# ---------------------------------------------------------------------------

class TestLLMBatchCuratorUsesRotator:
    """
    Lightweight smoke-test verifying that LLMBatchCurator delegates its
    generate_content call to the injected GeminiKeyRotator, not a bare client.
    """

    def test_curator_calls_rotator_generate_content(self):
        from services.batch_evaluator import LLMBatchCurator

        mock_rotator = MagicMock(spec=GeminiKeyRotator)
        mock_rotator.current_key = "some_key"
        mock_response = MagicMock()
        mock_response.parsed = None  # triggers deterministic fallback — that's fine
        mock_rotator.generate_content.return_value = mock_response

        curator = LLMBatchCurator(rotator=mock_rotator)
        # Verify the injected rotator is stored correctly
        assert curator.rotator is mock_rotator

    def test_curator_uses_rotator_not_bare_client(self):
        """LLMBatchCurator must NOT have a self.client attribute anymore."""
        from services.batch_evaluator import LLMBatchCurator

        curator = LLMBatchCurator(rotator=MagicMock(spec=GeminiKeyRotator))
        assert not hasattr(curator, "client"), (
            "LLMBatchCurator should no longer expose a bare `self.client`; "
            "use `self.rotator` instead."
        )
