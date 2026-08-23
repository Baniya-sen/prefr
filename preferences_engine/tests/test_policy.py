"""Deterministic tests for reflection policy write handlers.

Each test uses an isolated temporary policy corpus. No real policy file is
modified; the reflection loop itself is separately covered in test_reflector.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from preferences_engine import policy as P
from preferences_engine.evidence import derive_confidence, policy_confidence


class PolicyCorpusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policies = Path(self.tmp.name) / "policies"
        self.archive = self.policies / "archive"
        self.policies.mkdir()
        self.patchers = [
            mock.patch.object(P, "POLICIES", self.policies),
            mock.patch.object(P, "ARCHIVE_DIR", self.archive),
            mock.patch.object(P, "_valid_domains", return_value={"software", "git", "general"}),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def write_policy(self, policy_id: str, **overrides):
        data = {
            "id": policy_id,
            "title": policy_id,
            "body": f"Prefer {policy_id}.",
            "primary_domain": "software",
            "applies_to": ["software"],
            "priority": 60,
            "related": [],
            "exceptions": [],
            "evidence": {
                "positive_observations": [],
                "negative_observations": [],
                "representative_observations": [],
                "summary": "0 positive, 0 negative observation(s).",
            },
            "created_by": "reflection",
            "created_at": "2026-08-23",
            "updated_at": "2026-08-23",
            "last_reviewed": "2026-08-23",
        }
        data.update(overrides)
        with (self.policies / f"{policy_id}.yaml").open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        return data

    def load_policy(self, policy_id: str):
        with (self.policies / f"{policy_id}.yaml").open(encoding="utf-8") as f:
            return yaml.safe_load(f)


class TestEvidenceMath(PolicyCorpusTest):
    def test_uniform_prior_and_posterior(self):
        self.assertEqual(derive_confidence(0, 0), 0.5)
        self.assertEqual(derive_confidence(2, 0), 0.75)
        self.assertEqual(derive_confidence(0, 2), 0.25)
        self.assertEqual(policy_confidence({}), 0.5)

    def test_update_unions_observation_ids_idempotently(self):
        self.write_policy(
            "local_first",
            evidence={
                "positive_observations": ["s1:0"],
                "negative_observations": ["s0:2"],
            },
        )
        out = P.update_policies([{
            "id": "local_first",
            "evidence": {
                "positive_observations": ["s1:0", "s1:4"],
                "negative_observations": ["s0:2", "s1:5"],
            },
        }])[0]
        evidence = out["evidence"]
        self.assertEqual(evidence["positive_observations"], ["s1:0", "s1:4"])
        self.assertEqual(evidence["negative_observations"], ["s0:2", "s1:5"])
        self.assertEqual(evidence["representative_observations"], ["s1:0", "s1:4"])
        self.assertEqual(policy_confidence(out), 0.5)


class TestUpdatePolicies(PolicyCorpusTest):
    def test_only_whitelisted_fields_change(self):
        self.write_policy("keep")
        out = P.update_policies([{
            "id": "keep",
            "title": "Changed",
            "confidence": 1.0,
            "created_at": "1900-01-01",
            "id_renamed": "ignored",
        }])[0]
        self.assertEqual(out["id"], "keep")
        self.assertEqual(out["title"], "Changed")
        self.assertNotIn("confidence", out)
        self.assertEqual(str(out["created_at"]), "2026-08-23")

    def test_unknown_policy_reports_not_found(self):
        self.assertEqual(
            P.update_policies([{"id": "missing", "priority": 90}]),
            [{"id": "missing", "found": False}],
        )

    def test_invalid_domains_fall_back_general_and_priority_clamps(self):
        self.write_policy("keep")
        out = P.update_policies([{
            "id": "keep",
            "applies_to": ["not_a_domain"],
            "priority": 999,
        }])[0]
        self.assertEqual(out["applies_to"], ["general"])
        self.assertEqual(out["priority"], 100)


class TestArchivePolicies(PolicyCorpusTest):
    def test_archive_scrubs_refs_and_records_provenance(self):
        self.write_policy("retired")
        self.write_policy("related_ref", related=["retired"])
        self.write_policy("exception_ref", exceptions=["retired"])

        out = P.archive_policies([{"id": "retired"}])[0]
        self.assertTrue(out["archived"])
        self.assertEqual(
            out["referenced_by"],
            [
                {"policy": "exception_ref", "field": "exceptions"},
                {"policy": "related_ref", "field": "related"},
            ],
        )
        self.assertFalse((self.policies / "retired.yaml").exists())
        self.assertEqual(self.load_policy("related_ref")["related"], [])
        self.assertEqual(self.load_policy("exception_ref")["exceptions"], [])

        archived = list(self.archive.glob("retired.*.yaml"))
        self.assertEqual(len(archived), 1)
        record = yaml.safe_load(archived[0].read_text(encoding="utf-8"))
        self.assertEqual(record["archived_by"], "reflection")
        self.assertEqual(record["referenced_by"], out["referenced_by"])


class TestCreatePolicies(PolicyCorpusTest):
    def test_create_defaults_and_engine_owns_metadata(self):
        out = P.create_new_policies([{
            "id": "new_policy",
            "title": "New policy",
            "body": "Prefer new policies.",
            "applies_to": ["software"],
            "confidence": 1.0,
            "created_by": "attacker",
        }])[0]
        self.assertEqual(out["priority"], 50)
        self.assertEqual(out["created_by"], "reflection")
        self.assertNotIn("confidence", out)
        self.assertEqual(policy_confidence(out), 0.5)

    def test_create_replaces_rewires_then_archives(self):
        self.write_policy("old")
        self.write_policy("referrer", related=["old"], exceptions=["old"])

        out = P.create_new_policies([{
            "id": "new",
            "title": "New",
            "body": "Prefer new.",
            "priority": 80,
            "applies_to": ["software"],
            "replaces": ["old"],
        }])[0]

        self.assertEqual(out["replaced"], ["old"])
        self.assertFalse((self.policies / "old.yaml").exists())
        referrer = self.load_policy("referrer")
        self.assertEqual(referrer["related"], ["new"])
        self.assertEqual(referrer["exceptions"], ["new"])
        archived = yaml.safe_load(next(self.archive.glob("old.*.yaml")).read_text())
        self.assertEqual(archived["archive_reason"], "replaced by new")

    def test_invalid_or_duplicate_id_is_rejected(self):
        self.write_policy("existing")
        results = P.create_new_policies([
            {"id": "Not snake", "title": "x", "body": "x", "applies_to": ["software"]},
            {"id": "existing", "title": "x", "body": "x", "applies_to": ["software"]},
        ])
        self.assertFalse(results[0]["created"])
        self.assertIn("snake_case", results[0]["error"])
        self.assertFalse(results[1]["created"])
        self.assertEqual(results[1]["error"], "id already exists")


if __name__ == "__main__":
    unittest.main()
