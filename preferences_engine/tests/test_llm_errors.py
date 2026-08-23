"""Tests for LLM error handling in engine and reflector.

Verifies that when ctx.llm.complete_structured raises (trust gate, timeout,
rate limit, quota, generic), the error is classified and logged with enough
detail to diagnose — and that the caller's contract (re-raise for engine,
swallow for reflector) is preserved.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from preferences_engine.engine import PreferencesEngine
from preferences_engine.reflector import PreferenceReflector


class _FakeResp:
    def __init__(self, status_code):
        self.status_code = status_code


def _make_engine():
    eng = PreferencesEngine()
    eng.started = True
    return eng


class TestEngineLLMErrors(unittest.TestCase):
    def _call(self, engine, exc):
        """Call llm_completion with a ctx whose complete_structured raises."""
        ctx = SimpleNamespace()
        ctx.llm = SimpleNamespace()
        ctx.llm.complete_structured = mock.Mock(side_effect=exc)

        engine.llm_completion(
            ctx=ctx,
            user_messages=["test"],
            system_prompt="sys",
            classifier_model="m",
            classifier_provider="p",
        )

    def test_trust_error_logged_and_reraised(self):
        eng = _make_engine()
        exc = PermissionError("cannot override the model")

        with self.assertRaises(PermissionError):
            with mock.patch("preferences_engine.engine.logger") as log:
                self._call(eng, exc)

        # Trust-gate branch: logged at error with "trust gate" in the message.
        log.error.assert_called_once()
        msg = log.error.call_args[0][0]
        self.assertIn("trust gate", msg)

    def test_generic_error_logged_with_status_and_reraised(self):
        eng = _make_engine()
        exc = Exception("rate limit exceeded")
        exc.response = _FakeResp(429)

        with self.assertRaises(Exception):
            with mock.patch("preferences_engine.engine.logger") as log:
                self._call(eng, exc)

        log.error.assert_called_once()
        args = log.error.call_args
        # Format string includes type name, status, and message.
        self.assertIn("LLM call failed", args[0][0])
        self.assertIn("429", str(args))

    def test_error_without_response_status_is_none(self):
        eng = _make_engine()
        exc = TimeoutError("request timed out")

        with self.assertRaises(TimeoutError):
            with mock.patch("preferences_engine.engine.logger") as log:
                self._call(eng, exc)

        log.error.assert_called_once()
        # status should be None (no .response attr on TimeoutError).
        self.assertIn("None", str(log.error.call_args))


class TestReflectorLLMErrors(unittest.TestCase):
    def _make_reflector(self):
        # Bypass __init__ which loads a prompt.
        r = PreferenceReflector.__new__(PreferenceReflector)
        r._system_prompt = "sys"
        r._session = None
        r._cooldown = 0
        return r

    def _call_agent(self, reflector, exc):
        ctx = SimpleNamespace()
        ctx.llm = SimpleNamespace()
        ctx.llm.complete_structured = mock.Mock(side_effect=exc)

        return reflector._call_reflection_agent(
            ctx=ctx,
            system_prompt_and_history="sys",
            agent_turn_msgs=[],
            classifier_provider="p",
            classifier_model="m",
        )

    def test_trust_error_returns_empty_and_logs(self):
        r = self._make_reflector()
        exc = PermissionError("cannot override the provider")

        with mock.patch("preferences_engine.reflector.logger") as log:
            result = self._call_agent(r, exc)

        self.assertEqual(result, "")
        log.error.assert_called_once()
        self.assertIn("trust gate", log.error.call_args[0][0])

    def test_generic_error_returns_empty_and_logs_status(self):
        r = self._make_reflector()
        exc = Exception("quota exhausted")
        exc.response = _FakeResp(429)

        with mock.patch("preferences_engine.reflector.logger") as log:
            result = self._call_agent(r, exc)

        self.assertEqual(result, "")
        log.error.assert_called_once()
        self.assertIn("429", str(log.error.call_args))

    def test_timeout_returns_empty(self):
        r = self._make_reflector()
        exc = TimeoutError("timed out")

        with mock.patch("preferences_engine.reflector.logger") as log:
            result = self._call_agent(r, exc)

        self.assertEqual(result, "")
        # Reflector swallows — no exception, returns "".
        log.error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
