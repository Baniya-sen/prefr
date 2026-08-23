"""evidence.py — Pure evidence math for policy confidence.

Confidence is the posterior mean of a Beta(1,1) prior over (positive,
negative) observation counts — the standard Bayesian estimate for binary
evidence. A policy with no evidence starts at 0.5 (a true agnostic prior),
so confidence is always evidence-driven and never hand-seeded.

This is the ONLY place confidence is computed. ``priority`` is a separate,
judgment-driven axis and is never derived from evidence.
"""

from __future__ import annotations

from typing import Any


def derive_confidence(positive: int, negative: int) -> float:
    """Beta(1,1) posterior mean — the Laplace-smoothed confidence.

    0/0 -> 0.5 (agnostic), monotonic, bounded (0, 1). Never 0 or 1, so a
    single observation can't produce over-confidence.
    """
    p = max(0, int(positive))
    n = max(0, int(negative))
    return (p + 1) / (p + n + 2)


def policy_confidence(policy: dict[str, Any]) -> float:
    """Derive a policy's confidence from its evidence observation lists.

    Observation-id lists are the single source of truth; confidence is derived
    from their cardinalities. A policy carrying no observation lists (fresh or
    legacy) resolves to the uniform prior, 0.5.
    """
    evidence = policy.get("evidence")
    if isinstance(evidence, dict):
        pos = evidence.get("positive_observations")
        neg = evidence.get("negative_observations")
        if isinstance(pos, list) or isinstance(neg, list):
            return derive_confidence(len(pos or []), len(neg or []))
    return derive_confidence(0, 0)
