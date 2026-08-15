"""Tests for self-heal / fail-closed behaviour.

Deterministic — corrupt session files, missing schema, and hook failures are
simulated without network or LLM.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import preferences_engine.session as session_mod
from preferences_engine.session import Session, SessionManager
from preferences_engine import classifier as classifier_mod
from preferences_engine import config as config_mod


class TestSessionCorruptFile(unittest.TestCase):
    def _manager_with_file(self, content: str) -> SessionManager:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        session_file = Path(tmp.name) / "session.json"
        session_file.write_text(content, encoding="utf-8")
        patcher = mock.patch(
            "preferences_engine.session.SESSION_JSON", session_file
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return SessionManager()

    def test_corrupt_json_falls_back_to_fresh(self):
        m = self._manager_with_file("{ this is not valid json")
        self.assertIsInstance(m.session, Session)
        self.assertEqual(m.session.session_id, None)
        self.assertEqual(m.session.policies_injected, [])
        self.assertEqual(m.session.history_length, 0)

    def test_unknown_keys_are_dropped(self):
        m = self._manager_with_file(
            json.dumps({
                "session_id": "s1",
                "policies_injected": ["local_first"],
                "some_future_field": "ignored",
                "another_removed_field": 42,
            })
        )
        self.assertEqual(m.session.session_id, "s1")
        self.assertEqual(m.session.policies_injected, ["local_first"])
        # Unknown fields must not surface as attributes.
        self.assertFalse(hasattr(m.session, "some_future_field"))

    def test_non_dict_json_falls_back(self):
        m = self._manager_with_file("[1, 2, 3]")
        self.assertEqual(m.session.session_id, None)

    def test_missing_file_uses_fresh_defaults(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        session_file = Path(tmp.name) / "nonexistent.json"
        patcher = mock.patch(
            "preferences_engine.session.SESSION_JSON", session_file
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        m = SessionManager()
        self.assertIsInstance(m.session, Session)
        self.assertEqual(m.session.policies_injected, [])


class TestSaveFailureNonFatal(unittest.TestCase):
    def test_save_oserror_does_not_raise(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        session_file = Path(tmp.name) / "session.json"
        patcher = mock.patch(
            "preferences_engine.session.SESSION_JSON", session_file
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        m = SessionManager()
        m.ensure_session("s1", "model", "tg")
        # Simulate a write failure.
        with mock.patch.object(
            Path, "write_text", side_effect=OSError("disk full")
        ):
            m.deduplicate([{"id": "local_first", "body": "b"}])  # must not raise


class TestClassifierMissingSchema(unittest.TestCase):
    def test_missing_schema_returns_hardcoded_default(self):
        with mock.patch.object(
            classifier_mod, "SCHEMA", Path("/nonexistent/CLASSIFY_SCHEMA.json")
        ):
            default = classifier_mod._load_default()
        self.assertEqual(default["needs_policy"], False)
        self.assertEqual(default["classifier_confidence"], 0.0)
        self.assertEqual(default["domains"], [])
        self.assertEqual(default["interaction_mode"], "")

    def test_corrupt_schema_returns_hardcoded_default(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        tmp.write("{ not valid json")
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        with mock.patch.object(
            classifier_mod, "SCHEMA", Path(tmp.name)
        ):
            default = classifier_mod._load_default()
        self.assertEqual(default["needs_policy"], False)


if __name__ == "__main__":
    unittest.main()
