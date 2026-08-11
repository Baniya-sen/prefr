"""
Example Hermes pre_llm_call hook.
Adjust the return format to Hermes' hook API if needed.
"""

from preferences_engine.classifier import classify
from preferences_engine.evaluator import evaluator


def pre_llm_call(user_message: str):
    classification = classify(user_message)
    policies = evaluator.evaluate({
                "needs_policy": True,
                "classifier_confidence": 0.9,
                "domains": ["software"],
                "interaction_mode": "recommend",
            })

    if not policies:
        return {}

    injection = "\n\n".join(
        p.get("content", "")
        for p in policies
        if p.get("content")
    )

    return {
        "preferences_engine": {
            "classification": classification,
            "policies": policies,
        },
        "context": injection,
    }
