"""Unit tests for PreferencesEngine render methods (pure; no LLM/network/ctx)."""

import unittest

from preferences_engine.engine import PreferencesEngine


class TestRenderSchema(unittest.TestCase):
    def _engine(self) -> PreferencesEngine:
        # Build an instance WITHOUT __init__ to avoid log-file / runtime-dir side
        # effects, then run only the pure loaders (file reads, no logging).
        engine = object.__new__(PreferencesEngine)
        engine._load_domains()
        engine._load_interaction_modes()
        engine._load_schema()
        return engine

    def test_contains_field_names(self):
        out = self._engine()._render_schema()
        for field in (
            "needs_policy",
            "classifier_confidence",
            "domains",
            "interaction_mode",
        ):
            self.assertIn(field, out)

    def test_contains_allowed_domains(self):
        out = self._engine()._render_schema()
        for domain in ("software", "general"):
            self.assertIn(domain, out)

    def test_contains_allowed_interaction_modes(self):
        out = self._engine()._render_schema()
        for mode in ("recommend", "other"):
            self.assertIn(mode, out)


class TestRenderRegistries(unittest.TestCase):
    def _engine(self) -> PreferencesEngine:
        engine = object.__new__(PreferencesEngine)
        engine._load_domains()
        engine._load_interaction_modes()
        return engine

    def test_renders_domain_descriptions(self):
        out = self._engine()._render_registry("DOMAINS", self._engine()._domains)
        self.assertIn("## DOMAINS", out)
        self.assertIn("software", out)
        self.assertIn("general", out)

    def test_renders_interaction_mode_descriptions(self):
        engine = self._engine()
        out = engine._render_registry("INTERACTION MODES", engine._interaction_modes)
        self.assertIn("## INTERACTION MODES", out)
        self.assertIn("recommend", out)
        self.assertIn("troubleshoot", out)


class TestEnumDerivation(unittest.TestCase):
    def _engine(self) -> PreferencesEngine:
        engine = object.__new__(PreferencesEngine)
        engine._load_domains()
        engine._load_interaction_modes()
        engine._load_schema()
        return engine

    def test_domains_enum_derived_from_registry(self):
        engine = self._engine()
        derived = engine._json_schema["properties"]["domains"]["items"]["enum"]
        self.assertEqual(sorted(derived), sorted(engine._domains.keys()))

    def test_interaction_mode_enum_derived_from_registry(self):
        engine = self._engine()
        derived = engine._json_schema["properties"]["interaction_mode"]["enum"]
        self.assertEqual(sorted(derived), sorted(engine._interaction_modes.keys()))


if __name__ == "__main__":
    unittest.main()
