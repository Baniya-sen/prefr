"""
classifier.py

Thin wrapper around the PreferencesEngine.

Hermes should import this module instead of talking to llama-server
directly. All runtime/model management stays inside engine.py.
"""

from __future__ import annotations

import logging
from typing import Any

from preferences_engine.engine import engine

_REQUIRED_KEYS = {
    "needs_policy": False,
    "classifier_confidence": 0.0,
    "domains": [],
    "interaction_mode": "",
}


def _normalize(result: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure the classifier always returns a valid schema.
    """

    out = dict(_REQUIRED_KEYS)

    for key in _REQUIRED_KEYS:
        if key in result:
            out[key] = result[key]

    if not isinstance(out["domains"], list):
        out["domains"] = []

    try:
        out["classifier_confidence"] = float(out["classifier_confidence"])
    except Exception:
        out["classifier_confidence"] = 0.0

    out["needs_policy"] = bool(out["needs_policy"])
    out["interaction_mode"] = str(out["interaction_mode"])

    return out


def classify(user_message: str) -> dict[str, Any]:
    """
    Public API.

    Parameters
    ----------
    user_message:
        Raw user message from Hermes.

    Returns
    -------
    dict
        Deterministic classifier JSON.
    """

    try:
        result = engine.classify(user_message)
        return _normalize(result)

    except Exception:
        logging.exception("Classifier failed")

        return dict(_REQUIRED_KEYS)


def startup() -> None:
    """
    Warm the model during Hermes startup.
    """

    engine.start()


def shutdown() -> None:
    """
    Save slot state before Hermes exits.
    """

    engine.shutdown()
