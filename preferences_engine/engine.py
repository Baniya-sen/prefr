"""
engine.py — Preferences Engine Runtime (V1)

Loads the semantic classifier prompt, the domain + interaction-mode registries,
and the JSON output schema, renders them into a natural-language system prompt,
and requests JSON mode from Hermes' plugin LLM API.

Design (the three-way separation):
- prompt.py            = semantic instructions only (how to use the output)
- classification/domains.json         = domain registry (name -> description),
                                         dynamically extensible (reflection adds domains)
- classification/interaction_modes.json = interaction-mode registry, engine-defined/controlled
- classification/CLASSIFY_SCHEMA.json   = output contract (types + defaults);
                                         the domains + interaction_mode enums are
                                         DERIVED from the two registries at load time
- engine.py            = loads all, renders registries + schema into the prompt

Rule of thumb:
  The registry defines what exists. The schema defines what the model must
  output. The prompt explains how to use it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from preferences_engine.config import (
    DOMAINS,
    INTERACTION_MODES,
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
        self._load_domains()
        self._load_interaction_modes()
        self._load_schema()
        self._load_classifier_prompt()

    def _load_domains(self) -> None:
        with open(DOMAINS, "r", encoding="utf-8") as f:
            self._domains = json.load(f)

    def _load_interaction_modes(self) -> None:
        with open(INTERACTION_MODES, "r", encoding="utf-8") as f:
            self._interaction_modes = json.load(f)

    def _load_schema(self) -> None:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            schema = json.load(f)

        # Derive the enums from the registries — they are the single source of
        # truth for what values exist. The schema holds no hardcoded enum; a new
        # domain or interaction mode added to its registry automatically becomes
        # a valid classification value.
        schema["properties"]["domains"]["items"]["enum"] = list(self._domains.keys())
        schema["properties"]["interaction_mode"]["enum"] = list(self._interaction_modes.keys())

        self._json_schema = schema

    def _load_classifier_prompt(self) -> None:
        self._classifier_prompt = CLASSIFIER_PROMPT

    def _render_registry(self, title: str, registry: dict[str, Any]) -> str:
        """Render a registry (name -> description) into a natural-language block."""
        lines = [f"## {title}", "Available options:"]
        for name, meta in registry.items():
            description = str(meta.get("description", "")).strip()
            if description:
                lines.append(f"- {name}: {description}")
            else:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def _render_schema(self) -> str:
        """Render the JSON schema (types + enums) into a compact
        natural-language block the model can read directly.

        The schema JSON is the single source of truth for types and defaults;
        the enums are derived from the registries. Raw JSON Schema is
        validator-oriented and verbose — the model reads a flat enum list far
        more reliably and cheaply.
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

        system_prompt = (
            self._classifier_prompt
            + "\n\n"
            + self._render_registry("DOMAINS", self._domains)
            + "\n\n"
            + self._render_registry("INTERACTION MODES", self._interaction_modes)
            + "\n\n"
            + self._render_schema()
        )

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
