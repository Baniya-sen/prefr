"""Unit tests for preferences_engine.evaluator.PreferenceEvaluator (deterministic, reads policies/*.yaml)."""

import unittest

from preferences_engine.evaluator import MAX_PREFERENCES, PreferenceEvaluator


class TestEvaluateNeedsPolicyFalse(unittest.TestCase):
    def setUp(self):
        self.ev = PreferenceEvaluator()

    def test_returns_empty_list(self):
        self.assertEqual(
            self.ev.evaluate({"needs_policy": False, "domains": ["software"]}), []
        )

    def test_missing_needs_policy_defaults_false(self):
        self.assertEqual(self.ev.evaluate({}), [])


class TestEvaluateSoftwareDomain(unittest.TestCase):
    def setUp(self):
        self.ev = PreferenceEvaluator()

    def test_returns_non_empty_list_with_required_keys(self):
        res = self.ev.evaluate({"needs_policy": True, "domains": ["software"]})
        self.assertIsInstance(res, list)
        self.assertTrue(len(res) > 0)
        for policy in res:
            self.assertIn("id", policy)
            self.assertIn("weight", policy)
            self.assertIn("score", policy)

    def test_sorted_by_score_descending(self):
        res = self.ev.evaluate({"needs_policy": True, "domains": ["software"]})
        scores = [p["score"] for p in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            [p["id"] for p in res],
            ["local_first", "low_cost", "low_maintenance", "privacy_first"],
        )
        self.assertEqual(
            [p["weight"] for p in res],
            ["HIGH", "HIGH", "HIGH", "MEDIUM"],
        )


class TestMapWeight(unittest.TestCase):
    def setUp(self):
        self.ev = PreferenceEvaluator()

    def test_thresholds(self):
        self.assertEqual(self.ev._map_weight(200.0), "HIGH")
        self.assertEqual(self.ev._map_weight(160.0), "HIGH")
        self.assertEqual(self.ev._map_weight(159.9), "MEDIUM")
        self.assertEqual(self.ev._map_weight(120.0), "MEDIUM")
        self.assertEqual(self.ev._map_weight(119.9), "LOW")
        self.assertEqual(self.ev._map_weight(80.0), "LOW")
        self.assertEqual(self.ev._map_weight(79.9), "DROP")
        self.assertEqual(self.ev._map_weight(0.0), "DROP")


class TestComputeScore(unittest.TestCase):
    def setUp(self):
        self.ev = PreferenceEvaluator()

    def test_priority_plus_confidence_times_100(self):
        policy = {"priority": 90, "confidence": 0.7, "primary_domain": "software"}
        # 90 + 0.7*100 = 160; primary_domain not in {infrastructure} -> no bonus.
        self.assertEqual(self.ev._compute_score(policy, {"infrastructure"}), 160.0)

    def test_primary_domain_bonus(self):
        policy = {"priority": 90, "confidence": 0.7, "primary_domain": "software"}
        # 90 + 70 + 20 = 180 when primary_domain in domains.
        self.assertEqual(self.ev._compute_score(policy, {"software"}), 180.0)

    def test_no_primary_domain(self):
        policy = {"priority": 80, "confidence": 0.7}
        self.assertEqual(self.ev._compute_score(policy, {"software"}), 150.0)


class TestMaxPreferencesCap(unittest.TestCase):
    def test_caps_at_max_preferences(self):
        ev = PreferenceEvaluator()
        # Replace loaded policies with 8 synthetic ones, all matching "software".
        ev._policies = [
            {
                "id": f"policy_{i}",
                "title": f"Policy {i}",
                "body": f"body {i}",
                "primary_domain": "software",
                "applies_to": ["software"],
                "priority": 100 + i,
                "confidence": 0.5,
            }
            for i in range(8)
        ]
        res = ev.evaluate({"needs_policy": True, "domains": ["software"]})
        self.assertEqual(len(res), MAX_PREFERENCES)
        self.assertLessEqual(len(res), 6)
        scores = [p["score"] for p in res]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(
            [p["id"] for p in res],
            ["policy_7", "policy_6", "policy_5", "policy_4", "policy_3", "policy_2"],
        )


if __name__ == "__main__":
    unittest.main()
