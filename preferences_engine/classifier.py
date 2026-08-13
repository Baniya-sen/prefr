"""
classifier.py — Pure classification output normalization.

Takes an LLM result and returns a clean, schema-conformant
classification dict.

No LLM calls, no ctx, no engine, no provider logic.
"""

from __future__ import annotations

import json
from typing import Any


_DEFAULT = {
    "needs_policy": False,
    "classifier_confidence": 0.0,
    "domains": [],
    "interaction_mode": "",
}


def classify(result: Any) -> dict[str, Any]:
    parsed = getattr(result, "parsed", None)

    if isinstance(parsed, dict):
        return _normalize(parsed)

    text = getattr(result, "text", None)

    if isinstance(text, str):
        parsed = _parse_json(text)

        if isinstance(parsed, dict):
            return _normalize(parsed)

    return dict(_DEFAULT)


def _parse_json(text: str) -> Any:
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
