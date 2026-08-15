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
SCHEMAS_DIR = ROOT / "schemas"
SESSION_DIR = ROOT / "session"

SCHEMA = SCHEMAS_DIR / "CLASSIFY_SCHEMA.json"
SESSION_JSON = SESSION_DIR / "session.json"
LOG_FILE = RUNTIME_DIR / "preferences_engine.log"
