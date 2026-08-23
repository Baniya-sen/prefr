"""policy.py — Policy corpus read/write handlers for the reflection loop.

The corpus is one YAML file per policy under ``POLICIES``. These handlers are
the ONLY thing that writes to it. The reflection agent drives them through the
operation dispatch (view/update/archive/create); each returns the resulting
policy state, which the reflector feeds back to the agent as the authoritative
next-turn context.

Field ownership (the rule the whole engine enforces here):

    MODEL-WRITABLE — title, body, priority, applies_to, primary_domain,
        exceptions, related, evidence (observation ids only).
    ENGINE-OWNED   — id (immutable), confidence (derived from evidence),
        evidence counts (derived), representative_observations + summary
        (engine-maintained), created_by / created_at / updated_at /
        last_reviewed / replaced (provenance).

The model never sets engine-owned fields; anything it tries to set there is
silently ignored.
"""

from __future__ import annotations

import json
import re
import yaml

from datetime import date
from pathlib import Path
from typing import Any

from preferences_engine.config import ARCHIVE_DIR, DOMAINS, POLICIES

ResultPolicies = list[dict[str, Any]]

# Fields the reflection agent may write. Everything else is engine-owned.
MUTABLE_FIELDS = (
    "title",
    "body",
    "priority",
    "applies_to",
    "primary_domain",
    "exceptions",
    "related",
    "evidence",
)

# id is immutable and snake_case.
_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# Ids appear as references in exactly these two fields (not applies_to, which
# holds domain strings).
_REFERENCE_FIELDS = ("related", "exceptions")


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Corpus I/O
# ---------------------------------------------------------------------------

def _load_policies() -> ResultPolicies:
    policy_path = Path(POLICIES)
    policies: ResultPolicies = []

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


def _load_policy_by_id(policy_id: str) -> dict[str, Any] | None:
    path = Path(POLICIES) / f"{policy_id}.yaml"
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            policy = yaml.safe_load(f)
    except Exception:
        return None
    if isinstance(policy, dict) and policy.get("id"):
        return policy
    return None


def _save_policy(policy: dict[str, Any]) -> None:
    path = Path(POLICIES) / f"{policy['id']}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(policy, f, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Field coercion (model input -> clean, engine-safe values)
# ---------------------------------------------------------------------------

def _valid_domains() -> set[str]:
    try:
        return set(json.loads(Path(DOMAINS).read_text(encoding="utf-8")).keys())
    except Exception:
        return set()


def _dedup_ids(values: Any) -> list[str]:
    """Coerce an iterable of ids to a de-duplicated list of non-empty strings."""
    out: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = value.strip() if isinstance(value, str) else str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _coerce_priority(value: Any) -> int | None:
    """Clamp priority to [0, 100]; None when unparseable (caller decides)."""
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return None


def _coerce_domains(value: Any) -> list[str]:
    """Keep only registered domains; fall back to ``general`` when empty."""
    valid = _valid_domains()
    domains = [d for d in _dedup_ids(value) if d in valid]
    if not domains:
        domains = ["general"] if "general" in valid else sorted(valid)[:1]
    return domains


def _coerce_primary(value: Any, applies_to: list[str]) -> str:
    valid = _valid_domains()
    if isinstance(value, str) and value in valid:
        return value
    if applies_to:
        return applies_to[0]
    return "general" if "general" in valid else ""


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def _normalize_evidence(value: Any) -> dict[str, Any]:
    """Extract observation-id lists from the model's evidence input."""
    evidence = value if isinstance(value, dict) else {}
    return {
        "positive_observations": _dedup_ids(evidence.get("positive_observations")),
        "negative_observations": _dedup_ids(evidence.get("negative_observations")),
    }


def _summarize(positive: list[str], negative: list[str]) -> str:
    return f"{len(positive)} positive, {len(negative)} negative observation(s)."


def _merge_evidence(existing: Any, incoming: Any) -> dict[str, Any]:
    """Union incoming observation ids into the existing evidence block.

    Union (never replace) keeps evidence idempotent: re-sending an already-seen
    id on a later reflection pass cannot double-count it.
    """
    ex = existing if isinstance(existing, dict) else {}
    inc = _normalize_evidence(incoming)

    positive = _dedup_ids(
        list(_dedup_ids(ex.get("positive_observations")))
        + inc["positive_observations"]
    )
    negative = _dedup_ids(
        list(_dedup_ids(ex.get("negative_observations")))
        + inc["negative_observations"]
    )

    return {
        "positive_observations": positive,
        "negative_observations": negative,
        "representative_observations": list(positive),
        "summary": _summarize(positive, negative),
    }


# ---------------------------------------------------------------------------
# Reference graph (related / exceptions)
# ---------------------------------------------------------------------------

def _find_referrers(policy_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for policy in _load_policies():
        other = policy.get("id")
        if other == policy_id:
            continue
        for field in _REFERENCE_FIELDS:
            if policy_id in (policy.get(field) or []):
                out.append({"policy": other, "field": field})
    return out


def _scrub_references(policy_id: str) -> None:
    """Remove ``policy_id`` from every other policy's related/exceptions."""
    for policy in _load_policies():
        if policy.get("id") == policy_id:
            continue
        changed = False
        for field in _REFERENCE_FIELDS:
            refs = policy.get(field)
            if isinstance(refs, list) and policy_id in refs:
                policy[field] = [r for r in refs if r != policy_id]
                changed = True
        if changed:
            policy["updated_at"] = _today()
            _save_policy(policy)


def _rewire_references(old_id: str, new_id: str) -> None:
    """Replace every reference to ``old_id`` with ``new_id`` in other policies.

    Used by ``replaces`` on create: a successor policy inherits the references
    of the policy it supersedes, so no referrer is left pointing at an archived
    id. The dying policy itself is skipped (it is archived next).
    """
    for policy in _load_policies():
        if policy.get("id") in (old_id, new_id):
            continue
        changed = False
        for field in _REFERENCE_FIELDS:
            refs = policy.get(field)
            if not isinstance(refs, list):
                continue
            new_refs: list[str] = []
            for ref in refs:
                if ref == old_id:
                    if new_id not in new_refs:
                        new_refs.append(new_id)
                else:
                    new_refs.append(ref)
            if new_refs != refs:
                policy[field] = new_refs
                changed = True
        if changed:
            policy["updated_at"] = _today()
            _save_policy(policy)


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def view_policies(request: ResultPolicies) -> ResultPolicies:
    policy_by_id = {
        policy.get("id"): policy
        for policy in _load_policies()
    }

    result: ResultPolicies = []
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


def update_policies(request: ResultPolicies) -> ResultPolicies:
    result: ResultPolicies = []
    seen: set[str] = set()

    for item in request:
        if not isinstance(item, dict):
            continue
        policy_id = item.get("id")
        if not policy_id or policy_id in seen:
            continue
        seen.add(policy_id)

        policy = _load_policy_by_id(policy_id)
        if policy is None:
            result.append({"id": policy_id, "found": False})
            continue

        changed = False
        for field in MUTABLE_FIELDS:
            if field not in item:
                continue

            if field == "evidence":
                policy["evidence"] = _merge_evidence(
                    policy.get("evidence"), item["evidence"]
                )
                changed = True
            elif field == "priority":
                priority = _coerce_priority(item["priority"])
                if priority is not None:
                    policy["priority"] = priority
                    changed = True
            elif field == "applies_to":
                policy["applies_to"] = _coerce_domains(item["applies_to"])
                changed = True
            elif field == "primary_domain":
                policy["primary_domain"] = _coerce_primary(
                    item["primary_domain"], policy.get("applies_to", [])
                )
                changed = True
            elif field in _REFERENCE_FIELDS:
                policy[field] = _dedup_ids(item[field])
                changed = True
            else:  # title, body — plain strings
                value = item[field]
                if isinstance(value, str) and value.strip():
                    policy[field] = value.strip()
                    changed = True

        if changed:
            policy["updated_at"] = _today()
            policy["last_reviewed"] = _today()
            _save_policy(policy)

        result.append(policy)

    return result


def _archive_one(policy_id: str, reason: str = "") -> dict[str, Any]:
    policy = _load_policy_by_id(policy_id)
    if policy is None:
        return {"id": policy_id, "found": False}

    referrers = _find_referrers(policy_id)
    _scrub_references(policy_id)

    record = dict(policy)
    record["archived_at"] = _today()
    record["archived_by"] = "reflection"
    record["referenced_by"] = referrers
    if reason:
        record["archive_reason"] = reason

    archive_dir = Path(ARCHIVE_DIR)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / f"{policy_id}.{_today()}.yaml"
    with archive_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(record, f, sort_keys=False, allow_unicode=True)

    (Path(POLICIES) / f"{policy_id}.yaml").unlink(missing_ok=True)

    return {"id": policy_id, "archived": True, "referenced_by": referrers}


def archive_policies(request: ResultPolicies) -> ResultPolicies:
    result: ResultPolicies = []
    seen: set[str] = set()

    for item in request:
        if not isinstance(item, dict):
            continue
        policy_id = item.get("id")
        if not policy_id or policy_id in seen:
            continue
        seen.add(policy_id)
        result.append(_archive_one(policy_id))

    return result


def create_new_policies(request: ResultPolicies) -> ResultPolicies:
    result: ResultPolicies = []
    seen: set[str] = set()

    for item in request:
        if not isinstance(item, dict):
            continue
        policy_id = item.get("id")
        if not isinstance(policy_id, str) or not policy_id.strip():
            continue
        policy_id = policy_id.strip()
        if policy_id in seen:
            continue
        seen.add(policy_id)

        if not _ID_RE.match(policy_id):
            result.append({
                "id": policy_id,
                "created": False,
                "error": "id must be snake_case (lowercase letters, digits, underscores)",
            })
            continue
        if _load_policy_by_id(policy_id) is not None:
            result.append({
                "id": policy_id,
                "created": False,
                "error": "id already exists",
            })
            continue

        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        if not title or not body:
            result.append({
                "id": policy_id,
                "created": False,
                "error": "title and body are required",
            })
            continue

        priority = _coerce_priority(item.get("priority"))
        if priority is None:
            priority = 50

        applies_to = _coerce_domains(item.get("applies_to"))
        primary_domain = _coerce_primary(item.get("primary_domain"), applies_to)
        exceptions = _dedup_ids(item.get("exceptions"))
        related = _dedup_ids(item.get("related"))
        evidence = _merge_evidence({}, item.get("evidence"))

        policy: dict[str, Any] = {
            "id": policy_id,
            "title": title,
            "body": body,
            "primary_domain": primary_domain,
            "applies_to": applies_to,
            "priority": priority,
            "related": related,
            "exceptions": exceptions,
            "evidence": evidence,
            "created_by": "reflection",
            "created_at": _today(),
            "updated_at": _today(),
            "last_reviewed": _today(),
        }

        # replaces: rewire referrers to this policy, then archive the old ones.
        replaced: list[str] = []
        for old_id in _dedup_ids(item.get("replaces")):
            if old_id == policy_id:
                continue
            if _load_policy_by_id(old_id) is None:
                continue
            _rewire_references(old_id, policy_id)
            _archive_one(old_id, reason=f"replaced by {policy_id}")
            replaced.append(old_id)
        if replaced:
            policy["replaced"] = replaced

        _save_policy(policy)
        result.append(policy)

    return result
