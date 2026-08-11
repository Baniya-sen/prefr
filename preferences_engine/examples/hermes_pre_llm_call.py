"""
Example Hermes pre_llm_call hook.
Adjust the return format to Hermes' hook API if needed.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier import classify
from evaluator import evaluator


def pre_llm_call(user_message: str):
    classification = classify(user_message)
    policies = evaluator.evaluate(classification)

    if not policies:
        return {}

    injection = "\n\n".join(
        p.get("content", "") for p in policies if p.get("content")
    )

    return {
        "preferences_engine": {
            "classification": classification,
            "policies": policies,
        },
        "context": injection,
    }
