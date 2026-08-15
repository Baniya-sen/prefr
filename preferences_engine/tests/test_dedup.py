"""Tests for cross-turn preference dedup (SessionManager.deduplicate + formatter method).

Deterministic — no LLM, no network, no real ~/.hermes state. SESSION_JSON is
patched to a temp file per test.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from preferences_engine.session import SessionManager
from preferences_engine.formatter import PreferenceFormatter


def _policy(pid, **overrides):
    p = {"id": pid, "body": f"body of {pid}", "weight": "HIGH", "exceptions": []}
    p.update(overrides)
    return p


class TestDedupWithoutDuplicates(unittest.TestCase):
    def _manager(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        session_file = Path(tmp.name) / "session.json"
        patcher = mock.patch("preferences_engine.session.SESSION_JSON", session_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        m = SessionManager()
        m.ensure_session("session-1", "model", "telegram")
        return m

    def test_first_call_returns_all_as_new(self):
        m = self._manager()
        policies = [_policy("local_first"), _policy("low_cost")]
        new, referenced = m.deduplicate(policies)
        self.assertEqual([p["id"] for p in new], ["local_first", "low_cost"])
        # First turn: nothing was injected before -> referenced must be empty.
        self.assertEqual(referenced, [])

    def test_persisted_state_records_injected(self):
        m = self._manager()
        m.deduplicate([_policy("local_first"), _policy("low_cost")])
        self.assertEqual(
            sorted(m.session.policies_injected),
            ["local_first", "low_cost"],
        )


class TestDedupWithDuplicates(unittest.TestCase):
    def _manager(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        session_file = Path(tmp.name) / "session.json"
        patcher = mock.patch("preferences_engine.session.SESSION_JSON", session_file)
        patcher.start()
        self.addCleanup(patcher.stop)
        m = SessionManager()
        m.ensure_session("session-1", "model", "telegram")
        return m

    def test_full_duplicates_skipped(self):
        m = self._manager()
        m.deduplicate([_policy("local_first"), _policy("low_cost")])
        # Same policies again -> all already injected -> no new.
        new, referenced = m.deduplicate(
            [_policy("local_first"), _policy("low_cost")]
        )
        self.assertEqual(new, [])
        self.assertEqual(sorted(referenced), ["local_first", "low_cost"])

    def test_partial_duplicates(self):
        m = self._manager()
        m.deduplicate([_policy("local_first")])
        # local_first already injected, privacy_first is new.
        new, referenced = m.deduplicate(
            [_policy("local_first"), _policy("privacy_first")]
        )
        self.assertEqual([p["id"] for p in new], ["privacy_first"])
        # Only the already-injected one should be "referenced" (still relevant),
        # NOT the freshly-injected privacy_first.
        self.assertEqual(referenced, ["local_first"])
        self.assertNotIn("privacy_first", referenced)

    def test_blank_id_not_recorded(self):
        m = self._manager()
        m.deduplicate([_policy("")])
        self.assertEqual(m.session.policies_injected, [])


class TestFormatterMethod(unittest.TestCase):
    def test_full_when_no_referenced(self):
        out = PreferenceFormatter().format([_policy("local_first")], [])
        self.assertIn("<prefr-injection method='full'>", out)
        self.assertNotIn("still relevant", out)
        self.assertIn("</prefr-injection>", out)

    def test_compact_when_referenced(self):
        out = PreferenceFormatter().format(
            [_policy("privacy_first")], ["local_first"]
        )
        self.assertIn("<prefr-injection method='compact'>", out)
        self.assertIn("still relevant", out)
        self.assertIn("local_first", out)
        self.assertIn("</prefr-injection>", out)

    def test_empty_policies_returns_empty(self):
        self.assertEqual(PreferenceFormatter().format([], []), "")


if __name__ == "__main__":
    unittest.main()
