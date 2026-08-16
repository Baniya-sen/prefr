"""Unit tests for the injection window (PreferencePipeline._build_user_window)."""

import unittest

from preferences_engine.pipeline import PreferencePipeline


class TestBuildUserWindow(unittest.TestCase):
    def _window(self, history, current, window):
        # _build_user_window only touches self._content_to_text — no __init__
        # side effects needed.
        pipeline = object.__new__(PreferencePipeline)
        return pipeline._build_user_window(history, current, window=window)

    def test_window_1_returns_current_only(self):
        history = [
            {"role": "user", "content": "what vps should I use"},
            {"role": "assistant", "content": "here are options"},
            {"role": "user", "content": "use the second one"},
        ]
        out = self._window(history, "use the second one", window=1)
        self.assertEqual(out, ["use the second one"])

    def test_window_2_returns_current_plus_previous(self):
        history = [
            {"role": "user", "content": "what vps should I use"},
            {"role": "assistant", "content": "here are options"},
            {"role": "user", "content": "use the second one"},
        ]
        out = self._window(history, "use the second one", window=2)
        self.assertEqual(out, ["what vps should I use", "use the second one"])

    def test_window_3_returns_three_user_messages(self):
        history = [
            {"role": "user", "content": "plan a trip"},
            {"role": "assistant", "content": "where to"},
            {"role": "user", "content": "manali"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "make it 3 days"},
        ]
        out = self._window(history, "make it 3 days", window=3)
        self.assertEqual(out, ["plan a trip", "manali", "make it 3 days"])

    def test_skips_assistant_and_system(self):
        history = [
            {"role": "system", "content": "sys prompt"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "hello"},
        ]
        out = self._window(history, "hello", window=2)
        self.assertEqual(out, ["hello"])

    def test_current_message_deduped_from_history(self):
        # History already contains the current message as the last user turn.
        history = [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "current msg"},
        ]
        out = self._window(history, "current msg", window=2)
        self.assertEqual(out, ["first", "current msg"])

    def test_no_history(self):
        out = self._window(None, "just me", window=3)
        self.assertEqual(out, ["just me"])

    def test_content_as_block_list(self):
        history = [
            {"role": "user", "content": [{"type": "text", "text": "blocked msg"}]},
        ]
        out = self._window(history, "current", window=2)
        self.assertEqual(out, ["blocked msg", "current"])

    def test_none_content_returns_empty_not_crash(self):
        history = [{"role": "user", "content": None}]
        out = self._window(history, "current", window=2)
        self.assertEqual(out, ["current"])


if __name__ == "__main__":
    unittest.main()
