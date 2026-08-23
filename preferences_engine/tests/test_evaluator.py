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
            ["HIGH", "MEDIUM", "MEDIUM", "MEDIUM"],
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

    def test_score_uses_derived_confidence(self):
        policy = {
            "priority": 90,
            "primary_domain": "software",
            "evidence": {
                "positive_observations": ["a", "b"],
                "negative_observations": [],
            },
        }
        # confidence = (2+1)/(2+0+2) = 0.75; 90 + 75 = 165, no domain bonus.
        self.assertEqual(self.ev._compute_score(policy, {"infrastructure"}), 165.0)

    def test_no_evidence_defaults_to_uniform_prior(self):
        policy = {"priority": 90, "primary_domain": "software"}
        # confidence = 0.5 (uniform prior); 90 + 50 = 140.
        self.assertEqual(self.ev._compute_score(policy, {"infrastructure"}), 140.0)

    def test_primary_domain_bonus(self):
        policy = {
            "priority": 90,
            "primary_domain": "software",
            "evidence": {
                "positive_observations": ["a", "b"],
                "negative_observations": [],
            },
        }
        # confidence = 0.75; 90 + 75 + 20 = 185 when primary_domain in domains.
        self.assertEqual(self.ev._compute_score(policy, {"software"}), 185.0)

    def test_no_primary_domain(self):
        policy = {
            "priority": 80,
            "evidence": {
                "positive_observations": ["a", "b"],
                "negative_observations": [],
            },
        }
        # confidence = 0.75; 80 + 75 = 155.
        self.assertEqual(self.ev._compute_score(policy, {"software"}), 155.0)


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


class TestRelatedExpansion(unittest.TestCase):
    """Related-graph traversal gated by classifier_confidence."""

    def setUp(self):
        self.ev = PreferenceEvaluator()

    def test_related_depth_ladder(self):
        self.assertEqual(self.ev._related_depth(1.0), 3)
        self.assertEqual(self.ev._related_depth(0.8), 3)
        self.assertEqual(self.ev._related_depth(0.7), 2)
        self.assertEqual(self.ev._related_depth(0.6), 1)
        self.assertEqual(self.ev._related_depth(0.59), 0)
        self.assertEqual(self.ev._related_depth(0.5), 0)
        self.assertEqual(self.ev._related_depth(0.0), 0)

    def _ids(self, confidence: float) -> list[str]:
        res = self.ev.evaluate({
            "needs_policy": True,
            "classifier_confidence": confidence,
            "domains": ["development"],
        })
        return [p["id"] for p in res]

    def test_no_related_at_low_confidence(self):
        # depth 0 -> only the direct match.
        self.assertEqual(self._ids(0.5), ["local_first"])

    def test_related_depth_one(self):
        # depth 1 -> direct + hop-1 related (low_cost, privacy_first).
        self.assertEqual(self._ids(0.6), ["local_first", "low_cost", "privacy_first"])

    def test_related_depth_three_reaches_hop_two(self):
        # depth 3 -> reaches low_maintenance via low_cost (hop 2).
        self.assertEqual(
            self._ids(0.9),
            ["local_first", "low_cost", "privacy_first", "low_maintenance"],
        )

    def test_related_cycle_safe_no_duplicates(self):
        # local_first <-> privacy_first and low_cost <-> low_maintenance are cycles.
        ids = self._ids(0.9)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
