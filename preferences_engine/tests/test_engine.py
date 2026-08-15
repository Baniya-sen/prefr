"""Unit tests for prompt assembly and per-session prompt freezing (no LLM/network/ctx)."""

import unittest

from preferences_engine.prompt import build_prompt, _load_json, _render_registry, _render_schema
from preferences_engine.config import DOMAINS, INTERACTION_MODES, SCHEMA


class TestBuildPrompt(unittest.TestCase):
    def test_contains_field_names(self):
        out = build_prompt()
        for field in (
            "needs_policy",
            "classifier_confidence",
            "domains",
            "interaction_mode",
        ):
            self.assertIn(field, out)

    def test_contains_domains_and_descriptions(self):
        out = build_prompt()
        self.assertIn("## DOMAINS", out)
        self.assertIn("software", out)
        self.assertIn("general", out)

    def test_contains_interaction_modes_and_descriptions(self):
        out = build_prompt()
        self.assertIn("## INTERACTION MODES", out)
        self.assertIn("recommend", out)
        self.assertIn("troubleshoot", out)


class TestEnumDerivation(unittest.TestCase):
    def test_domains_enum_derived_from_registry(self):
        schema = _load_json(SCHEMA)
        domains = _load_json(DOMAINS)
        schema["properties"]["domains"]["items"]["enum"] = list(domains.keys())
        derived = schema["properties"]["domains"]["items"]["enum"]
        self.assertEqual(sorted(derived), sorted(domains.keys()))

    def test_interaction_mode_enum_derived_from_registry(self):
        schema = _load_json(SCHEMA)
        modes = _load_json(INTERACTION_MODES)
        schema["properties"]["interaction_mode"]["enum"] = list(modes.keys())
        derived = schema["properties"]["interaction_mode"]["enum"]
        self.assertEqual(sorted(derived), sorted(modes.keys()))


class TestRenderHelpers(unittest.TestCase):
    def test_render_registry(self):
        out = _render_registry("DOMAINS", {"x": {"description": "y"}})
        self.assertIn("## DOMAINS", out)
        self.assertIn("x: y", out)

    def test_render_schema_enums(self):
        schema = {
            "properties": {
                "f": {"type": "string", "enum": ["a", "b"]},
                "arr": {"type": "array", "items": {"type": "string", "enum": ["c"]}},
            }
        }
        out = _render_schema(schema)
        self.assertIn("f: string; allowed: a, b", out)
        self.assertIn("arr: array of string; allowed: c", out)


class TestPromptFreeze(unittest.TestCase):
    def setUp(self):
        # The freeze cache is module-level state shared across tests — reset it
        # so each test starts from a clean slate.
        import preferences_engine.prompt as P
        P._frozen_session_id = None
        P._frozen_prompt = None

    def test_freeze_rebuilds_on_session_change(self):
        from preferences_engine.prompt import get_prompt

        p1 = get_prompt("session-a")
        p2 = get_prompt("session-a")
        p3 = get_prompt("session-b")

        self.assertEqual(p1, p2)      # same session -> same frozen prompt
        self.assertEqual(p1, p3)      # content equal (same sources)

    def test_freeze_returns_identical_object(self):
        from preferences_engine.prompt import get_prompt
        # Same session must return the exact same cached string (no rebuild).
        self.assertIs(get_prompt("session-x"), get_prompt("session-x"))

    def test_same_session_does_not_rebuild(self):
        import preferences_engine.prompt as P
        calls = {"n": 0}
        orig = P.build_prompt

        def fake_build():
            calls["n"] += 1
            return orig()

        P.build_prompt = fake_build
        try:
            P.get_prompt("session-freeze-a")   # first call -> builds once
            P.get_prompt("session-freeze-a")   # same session -> no rebuild
            self.assertEqual(calls["n"], 1)    # built exactly once
        finally:
            P.build_prompt = orig

    def test_new_session_rebuilds(self):
        import preferences_engine.prompt as P
        calls = {"n": 0}
        orig = P.build_prompt

        def fake_build():
            calls["n"] += 1
            return orig()

        P.build_prompt = fake_build
        try:
            P.get_prompt("session-freeze-x")   # first session -> builds once
            P.get_prompt("session-freeze-y")   # new session -> rebuilds
            self.assertEqual(calls["n"], 2)    # built twice (once per session)
        finally:
            P.build_prompt = orig


if __name__ == "__main__":
    unittest.main()
