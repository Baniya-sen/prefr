"""
classifier.py — Pure classification output normalization.

Takes an LLM result and returns a clean, schema-conformant
classification dict.

No LLM calls, no ctx, no engine, no provider logic.
"""

from __future__ import annotations

import json
from typing import Any

from preferences_engine.config import SCHEMA


def _load_default() -> dict[str, Any]:
    """Derive the null classification from the output schema's ``default``
    values. The schema stays the single source of truth for field shape —
    add a field with a default there and it flows into the null fallback.

    If the schema file is missing or corrupt, fall back to a hardcoded null
    classification so the plugin still imports (fail-closed, no injection).
    """
    try:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, json.JSONDecodeError):
        return _HARDCODED_DEFAULT

    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return dict(_HARDCODED_DEFAULT)

    return {
        name: spec.get("default")
        for name, spec in properties.items()
        if isinstance(spec, dict)
    }


# Last-resort null classification, mirrors CLASSIFY_SCHEMA.json defaults.
_HARDCODED_DEFAULT: dict[str, Any] = {
    "needs_policy": False,
    "classifier_confidence": 0.0,
    "domains": [],
    "interaction_mode": "",
}


_DEFAULT = _load_default()


def classify(result: Any) -> dict[str, Any]:
    parsed = getattr(result, "parsed", None)

    if isinstance(parsed, dict):
        return _normalize(parsed)

    text = getattr(result, "text", None)

    if isinstance(text, str):
        parsed = parse_json(text)

        if isinstance(parsed, dict):
            return _normalize(parsed)

    return dict(_DEFAULT)


def parse_json(text: str) -> Any:
    text = text.strip()

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()

        if len(lines) >= 3:
            body = lines[1:-1]

            if lines[0].strip().lower() in {"```", "```json"}:
                try:
                    return json.loads("\n".join(body).strip())
                except json.JSONDecodeError:
                    pass

    return None


def _normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    result = dict(_DEFAULT)

    if "needs_policy" in parsed:
        result["needs_policy"] = _to_bool(
            parsed["needs_policy"]
        )

    if "classifier_confidence" in parsed:
        result["classifier_confidence"] = _to_confidence(
            parsed["classifier_confidence"]
        )

    if isinstance(parsed.get("domains"), list):
        result["domains"] = [
            str(domain)
            for domain in parsed["domains"]
        ]

    if "interaction_mode" in parsed:
        result["interaction_mode"] = str(
            parsed["interaction_mode"]
        )

    return result


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "true",
            "1",
            "yes",
        }

    return bool(value)


def _to_confidence(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0
