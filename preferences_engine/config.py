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

# Number of user messages the classifier sees (1 = current only, 2 = current +
# previous, etc.). Override: plugins.entries.prefr.window
INJECTION_WINDOW = int(_entry.get("window", 1))

# Classifier model/provider allowlists. These double as the Hermes trust gate:
# Hermes only permits a custom model/provider in a structured call when it is
# listed here (plugins.entries.prefr.llm.allowed_models / allowed_providers).
# Empty = no override -> the classifier runs on the host default (None).
ALLOWED_MODELS = list(_llm.get("allowed_models") or [])
ALLOWED_PROVIDERS = list(_llm.get("allowed_providers") or [])

# Our own selection: which model/provider the classifier actually runs on.
# Independent of the allowlist. When unset, falls back to allowed[0] (the
# first allowlisted entry); when that is empty too, None -> host default.
CLASSIFIER_MODEL = _entry.get("model") or None
CLASSIFIER_PROVIDER = _entry.get("provider") or None

MAX_TOKENS = 64
PURPOSE = "prefr.classifier"

# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------

REQUEST_TIMEOUT = 5

# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

ROOT = Path(__file__).parent

POLICIES = ROOT / "policies"
RUNTIME_DIR = ROOT / "runtime"
SESSION_DIR = ROOT / "session"
CLASSIFICATION_DIR = ROOT / "classification"

SCHEMA = CLASSIFICATION_DIR / "CLASSIFY_SCHEMA.json"
DOMAINS = CLASSIFICATION_DIR / "domains.json"
INTERACTION_MODES = CLASSIFICATION_DIR / "interaction_modes.json"
PROMPT = CLASSIFICATION_DIR / "prompt.md"
SESSION_JSON = SESSION_DIR / "session.json"
LOG_FILE = RUNTIME_DIR / "preferences_engine.log"
