"""Unit tests for preferences_engine.classifier (pure, deterministic, no LLM/network)."""

import unittest
from types import SimpleNamespace

from preferences_engine.classifier import (
    _DEFAULT,
    _normalize,
    parse_json,
    _to_bool,
    _to_confidence,
    classify,
)


class TestClassifyNullDefault(unittest.TestCase):
    def test_parsed_none_and_text_garbage_returns_default(self):
        result = SimpleNamespace(parsed=None, text="this is definitely not JSON")
        out = classify(result)
        self.assertEqual(out, _DEFAULT)
        # Must be a fresh dict, not the shared module default.
        self.assertIsNot(out, _DEFAULT)

    def test_missing_text_attribute_returns_default(self):
        result = SimpleNamespace(parsed=None)
        out = classify(result)
        self.assertEqual(out, _DEFAULT)


class TestClassifyParsedDict(unittest.TestCase):
    def test_parsed_valid_dict_is_normalized(self):
        result = SimpleNamespace(
            parsed={
                "needs_policy": True,
                "classifier_confidence": 0.8,
                "domains": ["software"],
                "interaction_mode": "recommend",
            },
            text=None,
        )
        out = classify(result)
        self.assertEqual(
            out,
            {
                "needs_policy": True,
                "classifier_confidence": 0.8,
                "domains": ["software"],
                "interaction_mode": "recommend",
            },
        )


class TestClassifyParsesTextJson(unittest.TestCase):
    def test_plain_json_text(self):
        result = SimpleNamespace(
            parsed=None,
            text=(
                '{"needs_policy": true, "classifier_confidence": 0.8, '
                '"domains": ["software"], "interaction_mode": "recommend"}'
            ),
        )
        out = classify(result)
        self.assertTrue(out["needs_policy"])
        self.assertEqual(out["classifier_confidence"], 0.8)
        self.assertEqual(out["domains"], ["software"])
        self.assertEqual(out["interaction_mode"], "recommend")

    def test_fenced_json_block(self):
        result = SimpleNamespace(
            parsed=None,
            text=(
                '```json\n{"needs_policy": true, "domains": ["general"], '
                '"interaction_mode": "learn", "classifier_confidence": 0.5}\n```'
            ),
        )
        out = classify(result)
        self.assertTrue(out["needs_policy"])
        self.assertEqual(out["domains"], ["general"])
        self.assertEqual(out["interaction_mode"], "learn")
        self.assertEqual(out["classifier_confidence"], 0.5)

    def test_plain_fence_without_language(self):
        result = SimpleNamespace(parsed=None, text='```\n{"needs_policy": false}\n```')
        out = classify(result)
        self.assertFalse(out["needs_policy"])


class TestParseJson(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_garbage_returns_none(self):
        self.assertIsNone(parse_json("not json at all"))

    def test_empty_returns_none(self):
        self.assertIsNone(parse_json(""))

    def test_fenced_json_strips_fences(self):
        self.assertEqual(parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_fenced_garbage_returns_none(self):
        self.assertIsNone(parse_json("```json\nthis is not json\n```"))


class TestToBool(unittest.TestCase):
    def test_bool_passthrough(self):
        self.assertIs(_to_bool(True), True)
        self.assertIs(_to_bool(False), False)

    def test_truthy_strings(self):
        for value in ["true", "TRUE", "True", "1", "yes", "YES"]:
            self.assertTrue(_to_bool(value), value)

    def test_falsy_strings(self):
        for value in ["false", "FALSE", "False", "0", "no", "", "   "]:
            self.assertFalse(_to_bool(value), value)

    def test_non_string_non_bool(self):
        self.assertTrue(_to_bool(1))
        self.assertTrue(_to_bool([0]))
        self.assertFalse(_to_bool(0))
        self.assertFalse(_to_bool(None))


class TestToConfidence(unittest.TestCase):
    def test_within_range(self):
        self.assertEqual(_to_confidence(0.5), 0.5)
        self.assertEqual(_to_confidence(0.0), 0.0)
        self.assertEqual(_to_confidence(1.0), 1.0)

    def test_clamp_high(self):
        self.assertEqual(_to_confidence(1.5), 1.0)
        self.assertEqual(_to_confidence(100.0), 1.0)

    def test_clamp_low(self):
        self.assertEqual(_to_confidence(-0.5), 0.0)
        self.assertEqual(_to_confidence(-100.0), 0.0)

    def test_string_coerced(self):
        self.assertEqual(_to_confidence("0.7"), 0.7)

    def test_invalid_returns_zero(self):
        self.assertEqual(_to_confidence("not a number"), 0.0)
        self.assertEqual(_to_confidence(None), 0.0)


class TestNormalize(unittest.TestCase):
    def test_empty_fills_defaults(self):
        out = _normalize({})
        self.assertEqual(out, _DEFAULT)

    def test_full_with_extra_keys_drops_unknown(self):
        out = _normalize(
            {
                "needs_policy": "yes",
                "classifier_confidence": 0.9,
                "domains": ["software", 123],
                "interaction_mode": "recommend",
                "extra_key": "should be dropped",
            }
        )
        self.assertEqual(
            out,
            {
                "needs_policy": True,
                "classifier_confidence": 0.9,
                "domains": ["software", "123"],
                "interaction_mode": "recommend",
            },
        )

    def test_only_emits_four_known_keys(self):
        out = _normalize({"needs_policy": True, "bogus": "x"})
        self.assertEqual(
            set(out.keys()),
            {"needs_policy", "classifier_confidence", "domains", "interaction_mode"},
        )


class TestDefault(unittest.TestCase):
    def test_default_shape(self):
        self.assertEqual(
            _DEFAULT,
            {
                "needs_policy": False,
                "classifier_confidence": 0.0,
                "domains": [],
                "interaction_mode": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
