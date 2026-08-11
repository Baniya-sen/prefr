"""
Preferences Engine Configuration (V1)

Central configuration for the Preferences Engine runtime.
Edit this file to change model/runtime behaviour.
"""

from pathlib import Path

# ------------------------------------------------------------------
# llama-server
# ------------------------------------------------------------------

LLAMA_SERVER = "http://127.0.0.1:8080"

# Single persistent classifier slot
SLOT_ID = 0

# ------------------------------------------------------------------
# Model
# ------------------------------------------------------------------

MODEL_NAME = "Qwen2.5-1.5B"

MAX_TOKENS = 64
TEMPERATURE = 0.1
TOP_K = 1
TOP_P = 0.9
MIN_P = 0.0
REPEAT_PENALTY = 1.05

# ------------------------------------------------------------------
# Runtime
# ------------------------------------------------------------------

REQUEST_TIMEOUT = 30
CACHE_PROMPT = True

# ------------------------------------------------------------------
# Files
# ------------------------------------------------------------------

ROOT = Path(__file__).parent

POLICIES = ROOT / "policies"
RUNTIME_DIR = ROOT / "runtime"
SCHEMAS_DIR = ROOT / "schemas"

SCHEMA = SCHEMAS_DIR / "CLASSIFY_SCHEMA.json"
PROMPT_HASH = RUNTIME_DIR / "prompt.sha256"
LOG_FILE = RUNTIME_DIR / "preferences_engine.log"
