"""PetroLedger ML Sandbox — GenAI Narration via Groq API.

Generates a plain-English narrative summary of a shift reconciliation
using Groq's fast inference (LLaMA 3.1 8B).  Reads ``GROQ_API_KEY``
from a ``.env`` file (via python-dotenv) or from the environment.

Returns ``None`` gracefully when the API key is missing or the call fails.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from ml/ root (or any parent)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Groq model to use
_DEFAULT_MODEL = "llama-3.1-8b-instant"


# ── System prompt ───────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are PetroLedger's AI analyst.  Given JSON data about a petrol-pump
shift reconciliation, write a concise 2-4 sentence summary in plain
English.  Mention the risk level, key anomalies (if any), likely cause,
and recommended action.  Be specific about monetary amounts and percentages.
Use Indian Rupee (₹) formatting.\
"""


# ── Service ─────────────────────────────────────────────────────────────


class NarrationService:
    """Generates natural-language summaries of shift reconciliation."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _DEFAULT_MODEL
        self._api_key: str | None = os.getenv("GROQ_API_KEY")

    @property
    def is_available(self) -> bool:
        """Whether the API key is configured."""
        return bool(self._api_key)

    def narrate(self, context: dict[str, Any]) -> str | None:
        """Generate a narration for the given reconciliation context.

        *context* should contain keys like ``shift_id``, ``risk_score``,
        ``anomalies``, ``isolation_forest``, ``attribution``, etc.

        Returns the narrative string, or ``None`` on failure / missing key.
        """
        if not self.is_available:
            logger.warning("GROQ_API_KEY not set — skipping narration.")
            return None

        try:
            from groq import Groq

            client = Groq(api_key=self._api_key)

            chat_completion = client.chat.completions.create(
                model=self.model,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            "Here is the shift reconciliation data:\n\n"
                            f"```json\n{json.dumps(context, indent=2, default=str)}\n```\n\n"
                            "Write a plain-English summary."
                        ),
                    },
                ],
            )

            text = chat_completion.choices[0].message.content
            logger.info("Narration generated (%d chars)", len(text))
            return text

        except Exception as exc:
            logger.error("Narration failed: %s", exc)
            return None
