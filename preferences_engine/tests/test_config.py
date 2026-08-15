"""Tests for config.py — plugin tunables from Hermes config.yaml.

Deterministic: monkeypatch hermes_cli.config.load_config to return canned
configs, then re-import config.py to observe the resolved values.
"""

import importlib
import unittest
from unittest import mock

import preferences_engine.config as config_mod


class TestConfigDefaults(unittest.TestCase):
    def setUp(self):
        # No plugins.entries.prefr -> all defaults.
        patcher = mock.patch(
            "hermes_cli.config.load_config",
            return_value={"plugins": {"entries": {}}},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cfg = importlib.reload(config_mod)

    def test_temperature_default(self):
        self.assertEqual(self.cfg.TEMPERATURE, 0.1)

    def test_window_default(self):
        self.assertEqual(self.cfg.INJECTION_WINDOW, 1)

    def test_allowed_lists_default_empty(self):
        self.assertEqual(self.cfg.ALLOWED_MODELS, [])
        self.assertEqual(self.cfg.ALLOWED_PROVIDERS, [])

    def test_classifier_selection_defaults_none(self):
        self.assertIsNone(self.cfg.CLASSIFIER_MODEL)
        self.assertIsNone(self.cfg.CLASSIFIER_PROVIDER)


class TestConfigOverride(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch(
            "hermes_cli.config.load_config",
            return_value={
                "plugins": {
                    "entries": {
                        "prefr": {
                            "temperature": 0.3,
                            "window": 3,
                            "model": "deepseek-v4-flash",
                            "provider": "opencode-go",
                            "llm": {
                                "allowed_models": ["a", "b", "c"],
                                "allowed_providers": ["x", "y"],
                            },
                        }
                    }
                }
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cfg = importlib.reload(config_mod)

    def test_temperature_override(self):
        self.assertEqual(self.cfg.TEMPERATURE, 0.3)

    def test_window_override(self):
        self.assertEqual(self.cfg.INJECTION_WINDOW, 3)

    def test_allowed_lists_override(self):
        self.assertEqual(self.cfg.ALLOWED_MODELS, ["a", "b", "c"])
        self.assertEqual(self.cfg.ALLOWED_PROVIDERS, ["x", "y"])

    def test_explicit_model_provider_override(self):
        self.assertEqual(self.cfg.CLASSIFIER_MODEL, "deepseek-v4-flash")
        self.assertEqual(self.cfg.CLASSIFIER_PROVIDER, "opencode-go")


class TestClassifierFallback(unittest.TestCase):
    def test_falls_back_to_allowed_first_when_explicit_unset(self):
        patcher = mock.patch(
            "hermes_cli.config.load_config",
            return_value={
                "plugins": {
                    "entries": {
                        "prefr": {
                            "llm": {
                                "allowed_models": ["second", "third"],
                                "allowed_providers": ["p1", "p2"],
                            },
                        }
                    }
                }
            },
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        cfg = importlib.reload(config_mod)
        # Explicit knob unset -> CLASSIFIER_* is None here; the fallback to
        # allowed[0] happens at the call site (__init__.py), so assert config
        # shape only.
        self.assertIsNone(cfg.CLASSIFIER_MODEL)
        self.assertEqual(cfg.ALLOWED_MODELS, ["second", "third"])


class TestConfigMalformed(unittest.TestCase):
    def test_missing_plugins_key(self):
        with mock.patch("hermes_cli.config.load_config", return_value=None):
            cfg = importlib.reload(config_mod)
        self.assertEqual(cfg.TEMPERATURE, 0.1)
        self.assertEqual(cfg.ALLOWED_MODELS, [])

    def test_load_config_raises(self):
        with mock.patch(
            "hermes_cli.config.load_config",
            side_effect=RuntimeError("no config"),
        ):
            cfg = importlib.reload(config_mod)
        self.assertEqual(cfg.TEMPERATURE, 0.1)
        self.assertEqual(cfg.INJECTION_WINDOW, 1)


if __name__ == "__main__":
    unittest.main()
