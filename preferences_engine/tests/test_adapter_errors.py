"""Local adapter error-injection tests.

The adapter is intentionally independent of Hermes. It emulates the failures
visible to prefr at ctx.llm.complete_structured's boundary, so error handling
can be exercised without exhausting a real provider quota.
"""

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
ADAPTER = ROOT / "temp" / "adapter.py"
SPEC = importlib.util.spec_from_file_location("prefr_adapter_under_test", ADAPTER)
assert SPEC is not None and SPEC.loader is not None
adapter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = adapter
SPEC.loader.exec_module(adapter)


class TestAdapterErrorInjection(unittest.TestCase):
    def setUp(self):
        self.llm = adapter.PluginLlm()

    def _call(self):
        return self.llm.complete_structured(
            instructions="classify",
            input=[{"type": "text", "text": "test"}],
            json_mode=True,
        )

    def test_timeout_simulation_raises_timeout_error(self):
        self.llm.simulate_error("timeout")

        with self.assertRaises(TimeoutError):
            self._call()

    def test_rate_limit_simulation_has_http_status(self):
        self.llm.simulate_error("rate_limit")

        with self.assertRaises(adapter.AdapterProviderError) as caught:
            self._call()

        self.assertEqual(caught.exception.response.status_code, 429)

    def test_trust_simulation_raises_permission_error(self):
        self.llm.simulate_error("trust")

        with self.assertRaises(PermissionError):
            self._call()

    def test_simulation_is_one_shot(self):
        self.llm.simulate_error("timeout")
        with self.assertRaises(TimeoutError):
            self._call()

        # The simulation is consumed, so the next call reaches normal provider
        # resolution rather than raising the injected timeout again.
        self.assertIsNone(self.llm._simulated_error)


if __name__ == "__main__":
    unittest.main()
