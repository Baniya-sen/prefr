"""
engine.py — Preferences Engine Runtime (V1)

Loads the semantic classifier prompt and the JSON output schema, renders the
schema (types + enums) into a natural-language block, and requests JSON mode
from Hermes' plugin LLM API.

Design:
- prompt.py            = semantic instructions only
- schemas/CLASSIFY_SCHEMA.json = output contract (types + enums), single source of truth
- engine.py            = loads both, renders schema into the prompt, requests JSON mode
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from preferences_engine.config import (
    LOG_FILE,
    MAX_TOKENS,
    REQUEST_TIMEOUT,
    SCHEMA,
    TEMPERATURE,
    PURPOSE,
)
from preferences_engine.prompt import CLASSIFIER_PROMPT


class PreferencesEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

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
        self._load_schema()
        self._load_classifier_prompt()

    def _load_schema(self) -> None:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            self._json_schema = json.load(f)

    def _load_classifier_prompt(self) -> None:
        self._classifier_prompt = CLASSIFIER_PROMPT

    def _render_schema(self) -> str:
        """Render the JSON schema (types + enums) into a compact
        natural-language block the model can read directly.

        The schema JSON stays the single source of truth, but raw JSON Schema
        is validator-oriented and verbose — the model reads a flat enum list
        far more reliably and cheaply.
        """
        props = self._json_schema.get("properties", {})

        lines = ["## OUTPUT SCHEMA", "Return one JSON object with exactly these fields:"]

        for name, spec in props.items():
            typ = spec.get("type", "string")
            if typ == "array":
                items = spec.get("items", {})
                item_type = items.get("type", "string")
                enum = items.get("enum")
                if enum:
                    lines.append(
                        f"- {name}: array of {item_type}; allowed: {', '.join(enum)}"
                    )
                else:
                    lines.append(f"- {name}: array of {item_type}")
            else:
                enum = spec.get("enum")
                if enum:
                    lines.append(f"- {name}: {typ}; allowed: {', '.join(enum)}")
                else:
                    lines.append(f"- {name}: {typ}")

        return "\n".join(lines)

    def start(self):
        self.started = True
        logging.info("Preferences Engine ready")

    def llm_completion(
        self,
        *,
        ctx: Any,
        user_message: str,
        classifier_provider: str | None = None,
        classifier_model: str | None = None,
        **kwargs,
    ) -> dict:
        if not self.started:
            self.start()

        system_prompt = self._classifier_prompt + "\n\n" + self._render_schema()

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
