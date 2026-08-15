"""Unit tests for preferences_engine.formatter.PreferenceFormatter (deterministic)."""

import unittest

from preferences_engine.formatter import PreferenceFormatter


def _policy(**overrides):
    policy = {
        "id": "local_first",
        "body": "Prefer local-first solutions.",
        "weight": "HIGH",
        "exceptions": [],
    }
    policy.update(overrides)
    return policy


class TestFormatEmpty(unittest.TestCase):
    def test_empty_list_returns_empty_string(self):
        self.assertEqual(PreferenceFormatter().format([]), "")

    def test_nothing_selected_returns_empty_string(self):
        # All policies dropped (nothing survives selection) -> empty.
        fmt = PreferenceFormatter(max_preferences=0)
        self.assertEqual(fmt.format([_policy()]), "")


class TestFormatBlock(unittest.TestCase):
    def test_delimiters(self):
        out = PreferenceFormatter().format([_policy()])
        self.assertTrue(out.startswith("<prefr-injection"))
        self.assertTrue(out.endswith("</prefr-injection>"))


class TestFormatPolicy(unittest.TestCase):
    def test_weight_id_and_body(self):
        out = PreferenceFormatter()._format_policy(_policy())
        self.assertIn("[HIGH] local_first", out)
        self.assertIn("Prefer local-first solutions.", out)

    def test_weight_is_uppercased(self):
        out = PreferenceFormatter()._format_policy(_policy(weight="medium"))
        self.assertIn("[MEDIUM]", out)

    def test_exceptions_block(self):
        policy = _policy(
            id="privacy_first",
            body="Keep data local.",
            weight="MEDIUM",
            exceptions=["company_projects", "health_emergency"],
        )
        out = PreferenceFormatter()._format_policy(policy)
        self.assertIn("[MEDIUM] privacy_first", out)
        self.assertIn(
            "Exceptions (Dampening effects) to the policy (privacy_first):", out
        )
        self.assertIn("- company_projects", out)
        self.assertIn("- health_emergency", out)

    def test_no_exceptions_no_block(self):
        out = PreferenceFormatter()._format_policy(_policy())
        self.assertNotIn("Exceptions", out)


class TestMaxPreferences(unittest.TestCase):
    def test_renders_at_most_max(self):
        policies = [_policy(id=f"p{i}", body=f"body {i}") for i in range(4)]
        fmt = PreferenceFormatter(max_preferences=2)
        out = fmt.format(policies)
        self.assertIn("p0", out)
        self.assertIn("p1", out)
        self.assertNotIn("p2", out)
        self.assertNotIn("p3", out)
        self.assertEqual(out.count("[HIGH]"), 2)


if __name__ == "__main__":
    unittest.main()
