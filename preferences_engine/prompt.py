"""
prompt.py — Prompt assembler.

Loads the semantic instruction text (prompt.md), the domain + interaction-mode
registries, and the output schema, and assembles the complete classifier system
prompt. The registries and schema are the single source of truth for what values
exist; the schema's enums are derived from them here.

Rule of thumb:
  The registry defines what exists. The schema defines what the model must
  output. The prompt explains how to use it.
"""

from __future__ import annotations

import json
from typing import Any

from preferences_engine.config import DOMAINS, INTERACTION_MODES, PROMPT, SCHEMA


def _load_json(path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_prompt_text() -> str:
    with open(PROMPT, "r", encoding="utf-8") as f:
        return f.read().strip()


def _render_registry(title: str, registry: dict[str, Any]) -> str:
    """Render a registry (name -> description) into a natural-language block."""
    lines = [f"## {title}", "Available options:"]
    for name, meta in registry.items():
        description = str(meta.get("description", "")).strip()
        lines.append(f"- {name}: {description}" if description else f"- {name}")
    return "\n".join(lines)


def _render_schema(schema: dict[str, Any]) -> str:
    """Render the JSON schema (types + enums) into a compact natural-language
    block. Raw JSON Schema is validator-oriented and verbose — the model reads a
    flat enum list far more reliably and cheaply."""
    props = schema.get("properties", {})

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


def build_prompt() -> str:
    """Assemble the full classifier system prompt from all sources.

    Re-reads every source file on each call, so a new domain or interaction mode
    added on disk is picked up the next time this runs (i.e. on the next session).
    """
    domains = _load_json(DOMAINS)
    interaction_modes = _load_json(INTERACTION_MODES)
    schema = _load_json(SCHEMA)

    # Derive the enums from the registries — single source of truth.
    schema["properties"]["domains"]["items"]["enum"] = list(domains.keys())
    schema["properties"]["interaction_mode"]["enum"] = list(interaction_modes.keys())

    return (
        _load_prompt_text()
        + "\n\n"
        + _render_registry("DOMAINS", domains)
        + "\n\n"
        + _render_registry("INTERACTION MODES", interaction_modes)
        + "\n\n"
        + _render_schema(schema)
    )


_frozen_session_id: str | None = None
_frozen_prompt: str | None = None


def get_prompt(session_id: str | None) -> str:
    """Return the frozen prompt for this session, building it once and reusing
    it for the session's lifetime. A new session id rebuilds fresh.

    The freeze lives here because it is the prompt's own behaviour — the prompt
    is what is frozen, so prompt.py owns the cache.
    """
    global _frozen_session_id, _frozen_prompt
    if session_id != _frozen_session_id or _frozen_prompt is None:
        _frozen_prompt = build_prompt()
        _frozen_session_id = session_id
    return _frozen_prompt
