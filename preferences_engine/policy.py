import yaml

from pathlib import Path
from typing import Any

from preferences_engine.config import POLICIES


def _load_policies() -> list[dict[str, Any]]:
    policy_path = Path(POLICIES)
    policies: list[dict[str, Any]] = []

    if policy_path.is_dir():
        for file in sorted(policy_path.glob("*.yaml")):
            try:
                with file.open("r", encoding="utf-8") as f:
                    policy = yaml.safe_load(f)
                    if not policy or "id" not in policy:
                        continue
                    policies.append(policy)
            except Exception:
                continue

    return policies


def view_policies(request: list[dict[str, Any]]) -> list[dict[str, Any]]:
    policy_by_id = {
        policy.get("id"): policy
        for policy in _load_policies()
    }

    requested_id = {
        item.get("id")
        for item in request
    }

    return [
        policy_by_id[policy_id]
        for policy_id in requested_id
        if policy_id in policy_by_id
    ]


def update_policies(request: list[dict[str, Any]]) -> None:
    return None


def archive_policies(request: list[dict[str, Any]]) -> None:
    return None


def create_new_policies(request: list[dict[str, Any]]) -> None:
    return None
