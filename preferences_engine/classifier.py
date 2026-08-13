"""
classifier.py — Pure classification.

Takes a structured LLM result and returns a valid classification dict.

No LLM call, no ctx, no engine, no llama. The LLM orchestration lives in
``llm_completions.py``; this module only turns its output into a clean,
schema-conformant classification.
"""

from __future__ import annotations

from typing import Any

_DEFAULT = {
    "needs_policy": False,
    "classifier_confidence": 0.0,
    "domains": [],
    "interaction_mode": "",
}


def _normalize(parsed: dict[str, Any]) -> dict[str, Any]:
    """Ensure a parsed dict always conforms to the classification schema."""
    out = dict(_DEFAULT)

    for key in _DEFAULT:
        if key in parsed:
            out[key] = parsed[key]

    if not isinstance(out["domains"], list):
        out["domains"] = []

    try:
        out["classifier_confidence"] = float(out["classifier_confidence"])
    except Exception:
        out["classifier_confidence"] = 0.0

    out["needs_policy"] = bool(out["needs_policy"])
    out["interaction_mode"] = str(out["interaction_mode"])

    return out


def classify(result: Any) -> dict[str, Any]:
    """Classify a structured LLM result into a clean dict.

    ``result`` is the object returned by ``ctx.llm.complete_structured()``
    (it has a ``.parsed`` attribute). If ``.parsed`` is missing or not a
    dict, the safe default classification is returned.
    """
    parsed = getattr(result, "parsed", None)

    if not isinstance(parsed, dict):
        return dict(_DEFAULT)

    return _normalize(parsed)
