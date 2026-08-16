"""Tests for pipeline early returns (no-policy, nothing-new-to-inject).

Deterministic — engine/LLM and session state are faked.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from preferences_engine.pipeline import PreferencePipeline


class TestEarlyReturnNoPolicy(unittest.TestCase):
    def test_needs_policy_false_skips_dedup_and_format(self):
        pl = PreferencePipeline()

        # Fake LLM result: classifier returns needs_policy=False.
        fake_result = SimpleNamespace(parsed={"needs_policy": False})
        pl.engine.llm_completion = mock.Mock(return_value=fake_result)

        # These must NOT be called.
        pl.session_manager.deduplicate = mock.Mock()
        pl.formatter.format = mock.Mock()

        out = pl.preference_pipeline(
            ctx=None, user_message="what is http", session_id="s1"
        )

        self.assertEqual(out, "")
        pl.session_manager.deduplicate.assert_not_called()
        pl.formatter.format.assert_not_called()

    def test_null_classification_skips_dedup_and_format(self):
        pl = PreferencePipeline()

        # No parsed/text -> classify returns null default (needs_policy False).
        pl.engine.llm_completion = mock.Mock(return_value=SimpleNamespace(
            parsed=None, text=None
        ))
        pl.session_manager.deduplicate = mock.Mock()
        pl.formatter.format = mock.Mock()

        out = pl.preference_pipeline(
            ctx=None, user_message="hello", session_id="s1"
        )

        self.assertEqual(out, "")
        pl.session_manager.deduplicate.assert_not_called()
        pl.formatter.format.assert_not_called()


class TestEarlyReturnNothingNew(unittest.TestCase):
    def test_all_already_injected_skips_format(self):
        pl = PreferencePipeline()

        # needs_policy=True so we pass the first guard.
        fake_result = SimpleNamespace(parsed={"needs_policy": True, "domains": ["software"]})
        pl.engine.llm_completion = mock.Mock(return_value=fake_result)

        # deduplicate returns no new policies -> everything already injected.
        pl.session_manager.deduplicate = mock.Mock(
            return_value=([], ["local_first", "low_cost"])
        )
        pl.formatter.format = mock.Mock()

        out = pl.preference_pipeline(
            ctx=None, user_message="use the second vps", session_id="s1"
        )

        self.assertEqual(out, "")
        pl.formatter.format.assert_not_called()

    def test_new_policies_do_call_format(self):
        pl = PreferencePipeline()

        fake_result = SimpleNamespace(parsed={"needs_policy": True, "domains": ["software"]})
        pl.engine.llm_completion = mock.Mock(return_value=fake_result)

        pl.session_manager.deduplicate = mock.Mock(
            return_value=([{"id": "local_first", "body": "b"}], [])
        )
        pl.formatter.format = mock.Mock(return_value="<prefr-injection>")

        out = pl.preference_pipeline(
            ctx=None, user_message="local photo backup", session_id="s1"
        )

        self.assertEqual(out, "<prefr-injection>")
        pl.formatter.format.assert_called_once()


if __name__ == "__main__":
    unittest.main()
