from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml  # pip install pyyaml

from config import POLICIES

MAX_PREFERENCES = 6
MIN_SCORE = 100


class Evaluator:

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
        elif score >= 130:
            return "MEDIUM"
        elif score >= 100:
            return "LOW"
        return "DROP"

    def evaluate(self, classification: dict[str, Any]) -> list[dict[str, Any]]:

        if not classification.get("needs_policy", False):
            return []

        domains = set(classification.get("domains", []))
        matches: list[tuple[float, dict[str, Any]]] = []

        for policy in self._policies:
            applies = set(policy.get("applies_to", []))

            if domains and applies.isdisjoint(domains):
                continue

            score = self._compute_score(policy, domains)

            if score < MIN_SCORE:
                continue

            matches.append((score, policy))

        matches.sort(key=lambda x: x[0], reverse=True)

        selected: list[dict[str, Any]] = []

        for score, policy in matches:
            weight = self._map_weight(score)
            if weight == "DROP":
                continue

            policy_copy = dict(policy)
            policy_copy["weight"] = weight

            selected.append(policy_copy)

            if len(selected) >= MAX_PREFERENCES:
                break

        return selected


evaluator = Evaluator()
