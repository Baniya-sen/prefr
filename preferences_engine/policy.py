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

    result: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in request:
        if not isinstance(item, dict):
            continue
        policy_id = item.get("id")
        if not policy_id or policy_id in seen:
            continue
        seen.add(policy_id)
        if policy_id in policy_by_id:
            result.append(policy_by_id[policy_id])
        else:
            result.append({"id": policy_id, "found": False})

    return result


def update_policies(request: list[dict[str, Any]]) -> None:
    return None


def archive_policies(request: list[dict[str, Any]]) -> None:
    return None


def create_new_policies(request: list[dict[str, Any]]) -> None:
    return None
