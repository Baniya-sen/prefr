from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # pip install pyyaml

from preferences_engine.config import POLICIES

MAX_PREFERENCES = 6
MIN_SCORE = 60
MAX_RELATED_DEPTH = 3


class PreferenceEvaluator:

    def __init__(self, policy_path: Path | str = POLICIES):
        self.policy_path = Path(policy_path)
        self._policies: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        self._policies = []

        if not self.policy_path.exists():
            return

        if self.policy_path.is_dir():
            for file in sorted(self.policy_path.glob("*.yaml")):
                try:
                    with file.open("r", encoding="utf-8") as f:
                        policy = yaml.safe_load(f)
                        if not policy or "id" not in policy:
                            continue
                        self._policies.append(policy)
                except Exception:
                    continue
        else:
            try:
                with self.policy_path.open("r", encoding="utf-8") as f:
                    self._policies = json.load(f)
            except Exception:
                self._policies = []

    def _compute_score(self, policy: dict[str, Any], domains: set[str]) -> float:
        priority = float(policy.get("priority", 0))
        confidence = float(policy.get("confidence", 0.0))
        score = priority + (confidence * 100)

        # Primary domain bonus: +20 if policy is specifically targeted
        primary = policy.get("primary_domain", "")
        if primary and primary in domains:
            score += 20

        return score

    def _map_weight(self, score: float) -> str:
        if score >= 160:
            return "HIGH"
        elif score >= 120:
            return "MEDIUM"
        elif score >= 80:
            return "LOW"
        return "DROP"

    def _related_depth(self, confidence: float) -> int:
        """How many hops of the `related` graph to expand, gated by classifier
        confidence. Higher confidence trusts the classification more and pulls
        a wider related set."""
        if confidence >= 0.8:
            return 3
        if confidence >= 0.7:
            return 2
        if confidence >= 0.6:
            return 1
        return 0

    def evaluate(self, classification: dict[str, Any]) -> list[dict[str, Any]]:

        if not classification.get("needs_policy", False):
            return []

        domains = set(classification.get("domains", []))
        confidence = float(classification.get("classifier_confidence", 0.0) or 0.0)
        depth = self._related_depth(confidence)
        by_id = {p.get("id"): p for p in self._policies if p.get("id")}

        # Direct matches: policy domain intersects the classified domain(s).
        direct: list[tuple[float, dict[str, Any]]] = []
        for policy in self._policies:
            applies = set(policy.get("applies_to", []))
            if domains and applies.isdisjoint(domains):
                continue
            score = self._compute_score(policy, domains)
            if score >= MIN_SCORE:
                direct.append((score, policy))
        direct.sort(key=lambda x: x[0], reverse=True)

        # Related expansion: BFS over `related`, depth-capped, cycle-safe.
        seen = {p.get("id") for _, p in direct}
        related: list[tuple[float, dict[str, Any]]] = []
        if depth > 0 and direct:
            frontier = [(p.get("id"), 1) for _, p in direct]
            while frontier:
                pid, hop = frontier.pop(0)
                if hop > depth:
                    continue
                policy = by_id.get(pid)
                if not policy:
                    continue
                for rel_id in policy.get("related", []):
                    if rel_id in seen:
                        continue
                    rel = by_id.get(rel_id)
                    if not rel:
                        continue
                    seen.add(rel_id)
                    score = self._compute_score(rel, domains)
                    related.append((score, rel))
                    frontier.append((rel_id, hop + 1))
        related.sort(key=lambda x: x[0], reverse=True)

        # Direct matches first, then related (secondary).
        collected = direct + related

        selected: list[dict[str, Any]] = []
        for score, policy in collected:
            weight = self._map_weight(score)
            if weight == "DROP":
                continue
            policy_copy = dict(policy)
            policy_copy["weight"] = weight
            policy_copy["score"] = score
            selected.append(policy_copy)
            if len(selected) >= MAX_PREFERENCES:
                break

        return selected
