"""
prompt.py — Prompt assembler (classification + reflection).

Loads the semantic instruction text, the registries, and the output schema, and
assembles the complete system prompts. The registries and schema are the single
source of truth for what values exist; the schema's enums are derived from them.

Two prompts are assembled and frozen per session:

- ``classification`` — the Phase 1 classifier prompt (prompt.md + domains +
  interaction modes + schema).
- ``reflection``    — the Phase 2 reflection-agent prompt (REFLECTION_PROMPT +
  REFLECTION_PROTOCOLS + domains + a policy index).

Rule of thumb:
  The registry defines what exists. The schema defines what the model must
  output. The prompt explains how to use it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from preferences_engine.config import (
    DOMAINS,
    INTERACTION_MODES,
    POLICIES,
    PROMPT,
    SCHEMA,
    REFLECTION_PROMPT,
    REFLECTION_PROTOCOLS,
    REFLECTION_SCHEMA,
)


def _load_json(path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_policies() -> list[dict[str, Any]]:
    """Load the current policy corpus (YAML, one file per policy). Kept local so
    prompt.py has no import-time dependency on policy.py."""
    policies: list[dict[str, Any]] = []
    policy_path = Path(POLICIES)
    if not policy_path.is_dir():
        return policies
    for file in sorted(policy_path.glob("*.yaml")):
        try:
            with file.open("r", encoding="utf-8") as f:
                policy = yaml.safe_load(f)
        except Exception:
            continue
        if policy and "id" in policy:
            policies.append(policy)
    return policies


def _read_text(path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _load_prompt_text() -> str:
    return _read_text(PROMPT)


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


def _render_reflection_schema(schema: dict[str, Any]) -> str:
    """Render the reflection output schema (method enum + request item fields)
    into a compact natural-language block. The full field semantics live in the
    protocol file; this is the machine-readable contract."""
    props = schema.get("properties", {})
    lines = ["## OUTPUT SCHEMA", "Return one JSON object:"]

    method = props.get("method", {})
    if isinstance(method, dict):
        enum = method.get("enum") or []
        if enum:
            lines.append(f"- method: one of {', '.join(enum)}")

    request = props.get("request", {})
    items = request.get("items", {}) if isinstance(request, dict) else {}
    item_props = items.get("properties", {}) if isinstance(items, dict) else {}
    fields: list[str] = []
    for name, spec in item_props.items():
        if not isinstance(spec, dict):
            continue
        fields.append(f"{name}:{spec.get('type', 'string')}")
    if fields:
        lines.append(
            f"- request: array of objects, each with fields {{{', '.join(fields)}}}"
        )

    return "\n".join(lines)


def _render_policy_index(policies: list[dict[str, Any]]) -> str:
    """Render the current policy corpus as a compact index (id/title/domain/
    priority). The reflection agent inspects full contents via the `view`
    operation rather than carrying them in the prompt."""
    lines = ["## CURRENT POLICIES (index — use `view` for full contents)"]
    if not policies:
        lines.append("(none)")
        return "\n".join(lines)
    for policy in policies:
        pid = policy.get("id")
        title = policy.get("title", "")
        domain = policy.get("primary_domain", "")
        priority = policy.get("priority", "")
        lines.append(f"- {pid} | {title} | domain={domain} | priority={priority}")
    return "\n".join(lines)


def _build_classification_prompt() -> str:
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


def _build_reflection_prompt() -> str:
    domains = _load_json(DOMAINS)
    schema = _load_json(REFLECTION_SCHEMA)

    # Order: prompt -> schema -> protocol -> domains -> policy index.
    parts = [
        _read_text(REFLECTION_PROMPT),
        _render_reflection_schema(schema),
        _read_text(REFLECTION_PROTOCOLS),
        _render_registry("DOMAINS", domains),
        _render_policy_index(_load_policies()),
    ]
    return "\n\n".join(p for p in parts if p)


def build_prompt(kind: str = "classification") -> str:
    """Assemble a system prompt. ``kind`` is ``"classification"`` (Phase 1) or
    ``"reflection"`` (Phase 2). Re-reads every source file on each call, so a
    new domain, policy, or instruction landed on disk is picked up the next
    time this runs (i.e. on the next session)."""
    if kind == "reflection":
        return _build_reflection_prompt()
    return _build_classification_prompt()


_frozen_session_id: str | None = None
_frozen_classification_prompt: str | None = None
_frozen_reflection_prompt: str | None = None


def get_prompt(session_id: str | None, kind: str = "classification") -> str:
    """Return the frozen prompt for this session and ``kind``.

    Builds BOTH prompts once per session and freezes them together — a new
    session id rebuilds both fresh. The freeze lives here because the prompt is
    what is frozen, so prompt.py owns the cache.
    """
    global _frozen_session_id, _frozen_classification_prompt, _frozen_reflection_prompt

    if (
        session_id != _frozen_session_id
        or _frozen_classification_prompt is None
        or _frozen_reflection_prompt is None
    ):
        _frozen_classification_prompt = build_prompt("classification")
        _frozen_reflection_prompt = build_prompt("reflection")
        _frozen_session_id = session_id

    if kind == "reflection":
        return _frozen_reflection_prompt
    return _frozen_classification_prompt
