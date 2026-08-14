import json
from dataclasses import dataclass
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


class SessionManager:
    def __init__(self):
        self.session: Session | None = None
        self._load_json()

    def _load_json(self):
        session_file = Path(SESSION_JSON)

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

    def start_session(self, session_id: str, model: str, platform: str, **kwargs) -> None:
        return

    def end_session(
        self,
        session_id: str,
        completed: bool,
        interrupted: bool,
        model: str,
        platform: str,
        **kwargs
    ) -> None:
        return

    def finalize_session(self, session_id: str | None, platform: str, **kwargs) -> None:
        return

    def reset_session(self, session_id: str, platform: str, **kwargs) -> None:
        return


@dataclass
class Session:
    session_id: str | None = None
    started_at: str | None = None
    last_seen: str | None = None
    turn_count: int = 0
    model: str | None = None
    platform: str | None = None
