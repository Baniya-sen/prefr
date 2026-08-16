import json
from dataclasses import dataclass, asdict, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from preferences_engine.config import SESSION_JSON


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionManager:
    def __init__(self):
        self.session: Session | None = None
        self._load_json()

    def _load_json(self):
        session_file = Path(SESSION_JSON)
        session_file.parent.mkdir(parents=True, exist_ok=True)

        # Fresh defaults; overwritten by a valid, known-schema file.
        session_json = asdict(Session())

        if session_file.is_file():
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    # Drop unknown keys so Session(**...) never raises on a
                    # stale/forward-compatible schema (removed or renamed fields).
                    known = {f.name for f in fields(Session)}
                    session_json = {k: v for k, v in loaded.items() if k in known}
            except (OSError, json.JSONDecodeError):
                # Corrupt or half-written file -> fall back to fresh defaults.
                pass

        self.session = Session(**session_json)

    def _save_json(self) -> None:
        try:
            session_file = Path(SESSION_JSON)
            session_file.parent.mkdir(parents=True, exist_ok=True)
            session_file.write_text(
                json.dumps(asdict(self.session), indent=2),
                encoding="utf-8",
            )
        except OSError:
            # Disk full / permissions — never crash the turn over state that is
            # not critical to the injection itself.
            pass

    def ensure_session(self, session_id: str | None, model: str | None, platform: str, **kwargs) -> None:
        """Reconcile identity: re-init only when the current id is stale or None."""
        if self.session is None or self.session.session_id != session_id:
            self.session = Session(
                session_id=session_id,
                policies_injected=[],
                started_at=_now(),
                last_seen=_now(),
                turn_count=0,
                model=model,
                platform=platform,
            )
            self._save_json()

    def start_session(self, session_id: str, model: str, platform: str, **kwargs) -> None:
        self.ensure_session(session_id, model, platform)

    def end_session(
        self,
        session_id: str,
        completed: bool,
        interrupted: bool,
        model: str,
        platform: str,
        **kwargs
    ) -> None:
        self.ensure_session(session_id, model, platform)
        self.session.turn_count += 1
        self.session.last_seen = _now()
        self._save_json()

    def finalize_session(self, session_id: str | None, platform: str, **kwargs) -> None:
        self.session = Session()
        self._save_json()

    def reset_session(self, session_id: str, platform: str, **kwargs) -> None:
        self.ensure_session(session_id, None, platform)

    def detect_compaction(self, conversation_history: list[Any] | None) -> bool:
        """Detect a context compaction by comparing the incoming history length
        against the stored anchor. History grows monotonically between turns and
        shrinks only when compaction collapses a long middle into a summary — so
        a shrink means our injected blocks were dropped, and we clear the
        already-injected set so they get re-injected.

        Takes the raw history and derives length itself; callers pass it through.
        """
        history_len = len(conversation_history or [])
        anchor = self.session.history_length or 0

        compacted = history_len < anchor
        if compacted:
            self.session.policies_injected = []

        self.session.history_length = history_len
        self._save_json()
        return compacted

    def deduplicate(
            self,
            policies: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return (new_policies, referenced).

        new_policies = policies NOT yet injected this session (render full body).
        referenced    = policies ALREADY injected this session that are still
                        relevant (reference by id, don't re-inject).
        """
        injected = list(self.session.policies_injected or [])

        new_policies: list[dict[str, Any]] = []
        referenced: list[str] = []

        for policy in policies:
            policy_id = str(policy.get("id", "")).strip()
            if not policy_id:
                continue
            if policy_id in injected:
                referenced.append(policy_id)
            else:
                new_policies.append(policy)
                injected.append(policy_id)

        self.session.policies_injected = injected
        self._save_json()

        return new_policies, referenced



@dataclass
class Session:
    session_id: str | None = None
    policies_injected: list[str] = field(default_factory=list)
    history_length: int = 0
    started_at: str | None = None
    last_seen: str | None = None
    turn_count: int = 0
    model: str | None = None
    platform: str | None = None
