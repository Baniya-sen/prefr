"""
Preferences Engine Configuration (V1)

Central configuration for the Preferences Engine runtime.

Tunables are read from the Hermes config.yaml under ``plugins.entries.prefr``.
If a key is defined there, it is used; otherwise the hardcoded default below
applies. Paths are internal and not user-configurable.
"""

from pathlib import Path

# ------------------------------------------------------------------
# Hermes config (plugins.entries.prefr) — overridable, with defaults
# ------------------------------------------------------------------

def _plugin_entry() -> dict:
    """Read ``plugins.entries.prefr`` from Hermes config.yaml, or {} on any
    failure (missing file, not under Hermes, malformed)."""
    try:
        from hermes_cli.config import load_config
        cfg = load_config() or {}
        entries = (cfg.get("plugins") or {}).get("entries") or {}
        return entries.get("prefr") or {}
    except Exception:
        return {}


_entry = _plugin_entry()
_llm = _entry.get("llm") or {}

# Classifier LLM temperature. Override: plugins.entries.prefr.temperature
TEMPERATURE = float(_entry.get("temperature", 0.1))
REFLECTOR_TEMPERATURE = 0.6

# Number of user messages the classifier sees (1 = current only, 2 = current +
# previous, etc.). Override: plugins.entries.prefr.window
INJECTION_WINDOW = int(_entry.get("window", 1))

# Classifier model/provider allowlists. These are consulted ONLY AFTER the
# trust-gate booleans below are opened; they do NOT gate access by themselves.
# Empty = no allowlist filtering (any value passes, subject to the gate).
ALLOWED_MODELS = list(_llm.get("allowed_models") or [])
ALLOWED_PROVIDERS = list(_llm.get("allowed_providers") or [])

# The actual Hermes trust gate. Hermes raises PluginLlmTrustError (swallowed by
# our fail-closed hook -> silent no-inject) unless the matching boolean is true
# when we request a model/provider override. Both default false (Hermes default).
ALLOW_MODEL_OVERRIDE = bool(_llm.get("allow_model_override", False))
ALLOW_PROVIDER_OVERRIDE = bool(_llm.get("allow_provider_override", False))

# Our own selection: which model/provider the classifier actually runs on.
# Independent of the allowlist. When unset, falls back to allowed[0] (the
# first allowlisted entry); when that is empty too, None -> host default.
CLASSIFIER_MODEL = _entry.get("model") or None
CLASSIFIER_PROVIDER = _entry.get("provider") or None

REFLECTION_TURN_COUNT = 15
MAX_REFLECTION_STEPS = 16

MAX_TOKENS = 64
PURPOSE = "prefr.classifier"
REFLECTOR_PURPOSE = "prefr.reflection"

# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------

REQUEST_TIMEOUT = 8

# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

ROOT = Path(__file__).parent

POLICIES = ROOT / "policies"
RUNTIME_DIR = ROOT / "runtime"
SESSION_DIR = ROOT / "session"
CLASSIFICATION_DIR = ROOT / "classification"
REFLECTION_DIR = ROOT / "reflection"

SCHEMA = CLASSIFICATION_DIR / "CLASSIFY_SCHEMA.json"
DOMAINS = CLASSIFICATION_DIR / "domains.json"
INTERACTION_MODES = CLASSIFICATION_DIR / "interaction_modes.json"
PROMPT = CLASSIFICATION_DIR / "prompt.md"
SESSION_JSON = SESSION_DIR / "session.json"
REFLECTION_SCHEMA = REFLECTION_DIR / "REFLECTION_SCHEMA.json"
REFLECTION_PROMPT = REFLECTION_DIR / "REFLECTION_PROMPT.md"
REFLECTION_PROTOCOLS = REFLECTION_DIR / "REFLECTION_PROTOCOL.md"
LOG_FILE = RUNTIME_DIR / "preferences_engine.log"
