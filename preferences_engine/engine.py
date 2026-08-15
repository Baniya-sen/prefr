"""
engine.py — Preferences Engine Runtime (V1)

Calls Hermes' plugin LLM API in JSON mode with a caller-supplied system prompt.
The engine is dumb: it does not build or cache the prompt, and knows nothing
about sessions. prompt.py builds/freezes the prompt; the pipeline passes it here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from preferences_engine.config import (
    LOG_FILE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    TEMPERATURE,
    PURPOSE,
)


class PreferencesEngine:
    def __init__(self):
        if getattr(self, "_init", False):
            return

        self._init = True

        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

        self.started = False

    def start(self):
        self.started = True
        logging.info("Preferences Engine ready")

    def llm_completion(
        self,
        *,
        ctx: Any,
        user_message: str,
        system_prompt: str,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
        **kwargs,
    ) -> dict:
        if not self.started:
            self.start()

        return ctx.llm.complete_structured(
            instructions="Classify the user message below.",
            system_prompt=system_prompt,
            json_mode=True,
            input=[{"type": "text", "text": user_message}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            purpose=PURPOSE,
            provider=classifier_provider,
            model=classifier_model,
            timeout=REQUEST_TIMEOUT,
        )
