import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

from preferences_engine.config import SESSION_JSON

_DEFAULT_SESSION = {
  "session_id": None,
  "started_at": None,
  "last_seen": None,
  "turn_count": 0,
  "model": None,
  "platform": None
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionManager:
    def __init__(self):
        self.session: Session | None = None
        self._load_json()

    def _load_json(self):
        session_file = Path(SESSION_JSON)
        session_file.parent.mkdir(parents=True, exist_ok=True)

        if session_file.is_file():
            with open(session_file, "r", encoding="utf-8") as f:
                session_json = json.load(f)
        else:
            session_json = _DEFAULT_SESSION
            session_file.write_text(
                json.dumps(_DEFAULT_SESSION, indent=2),
                encoding="utf-8"
            )

        self.session = Session(**session_json)

    def _save_json(self) -> None:
        session_file = Path(SESSION_JSON)
        session_file.write_text(
            json.dumps(asdict(self.session), indent=2),
            encoding="utf-8",
        )

    def ensure_session(self, session_id: str | None, model: str | None, platform: str, **kwargs) -> None:
        """Reconcile identity: re-init only when the current id is stale or None."""
        if self.session is None or self.session.session_id != session_id:
            self.session = Session(
                session_id=session_id,
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


@dataclass
class Session:
    session_id: str | None = None
    started_at: str | None = None
    last_seen: str | None = None
    turn_count: int = 0
    model: str | None = None
    platform: str | None = None
