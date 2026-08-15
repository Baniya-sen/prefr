"""
Preferences Engine Configuration (V1)

Central configuration for the Preferences Engine runtime.
Edit this file to change model/runtime behaviour.
"""

from pathlib import Path

MAX_TOKENS = 64
TEMPERATURE = 0.1
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
