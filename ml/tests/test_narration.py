"""Tests for GenAI narration service."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.narration import NarrationService


class TestAvailability:
    def test_unavailable_without_key(self):
        with patch.dict("os.environ", {}, clear=True):
            svc = NarrationService()
            svc._api_key = None
            assert svc.is_available is False

    def test_available_with_key(self):
        svc = NarrationService()
        svc._api_key = "test-key-123"
        assert svc.is_available is True


def _make_mock_groq(response_text: str = "Summary", *, side_effect=None):
    """Create a mock groq module with a configured Groq client."""
    mock_message = MagicMock()
    mock_message.content = response_text

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    mock_client = MagicMock()
    if side_effect:
        mock_client.chat.completions.create.side_effect = side_effect
    else:
        mock_client.chat.completions.create.return_value = mock_completion

    mock_module = MagicMock()
    mock_module.Groq.return_value = mock_client
    return mock_module, mock_client


class TestNarrate:
    def test_returns_none_without_key(self):
        svc = NarrationService()
        svc._api_key = None
        result = svc.narrate({"shift_id": "test", "risk_score": 0.5})
        assert result is None

    def test_mocked_api_returns_narration(self):
        svc = NarrationService()
        svc._api_key = "test-key-123"

        mock_module, mock_client = _make_mock_groq(
            "This shift shows a high risk of worker skimming with ₹3,000 variance."
        )

        with patch.dict("sys.modules", {"groq": mock_module}):
            result = svc.narrate({
                "shift_id": "abc-123",
                "risk_score": 0.8,
                "anomalies": [{"type": "CASH_VARIANCE_HIGH", "severity": "high"}],
            })

            assert result is not None
            assert "₹3,000" in result
            mock_client.chat.completions.create.assert_called_once()

    def test_graceful_failure_on_api_error(self):
        svc = NarrationService()
        svc._api_key = "test-key-123"

        mock_module, _ = _make_mock_groq(side_effect=Exception("API timeout"))

        with patch.dict("sys.modules", {"groq": mock_module}):
            result = svc.narrate({"shift_id": "test"})
            assert result is None

    def test_narration_context_passed_to_api(self):
        svc = NarrationService()
        svc._api_key = "test-key-123"

        mock_module, mock_client = _make_mock_groq("Summary")

        context = {
            "shift_id": "shift-xyz",
            "risk_score": 0.6,
            "anomalies": [],
            "attribution": {"class": "worker", "confidence": 0.85},
        }

        with patch.dict("sys.modules", {"groq": mock_module}):
            svc.narrate(context)

            call_args = mock_client.chat.completions.create.call_args
            user_msg = call_args[1]["messages"][1]["content"]
            assert "shift-xyz" in user_msg
            assert "worker" in user_msg
