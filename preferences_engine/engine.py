"""
engine.py - Preferences Engine Runtime (V1)

Simple singleton runtime for a local llama-server classifier.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

import requests

from preferences_engine.config import (
    CACHE_PROMPT,
    LLAMA_SERVER,
    LOG_FILE,
    MAX_TOKENS,
    MIN_P,
    PROMPT_HASH,
    REPEAT_PENALTY,
    REQUEST_TIMEOUT,
    SCHEMA,
    SLOT_ID,
    TEMPERATURE,
    TOP_K,
    TOP_P,
)
from preferences_engine.prompt import CLASSIFIER_PROMPT


class PreferencesEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_init", False):
            return

        self._init = True

        Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )

        self.session = requests.Session()
        self.started = False
        self._json_schema = self._load_schema()

    def _load_schema(self) -> dict:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            return json.load(f)

    def start(self):
        self._health()

        if self._prompt_changed():
            self.erase_slot()

        if not self.restore_slot():
            self._prime_prompt()
            self.save_slot()

        self.started = True
        logging.info("Preferences Engine ready")

    def classify(self, user_text: str) -> dict:
        if not self.started:
            self.start()

        prompt = (
            CLASSIFIER_PROMPT
            + "\n\nUser: "
            + user_text
            + "\nAssistant:"
        )

        r = self.session.post(
            f"{LLAMA_SERVER}/completion",
            json={
                "prompt": prompt,
                "slot_id": SLOT_ID,
                "cache_prompt": CACHE_PROMPT,
                "temperature": TEMPERATURE,
                "top_k": TOP_K,
                "top_p": TOP_P,
                "min_p": MIN_P,
                "repeat_penalty": REPEAT_PENALTY,
                "stream": False,
                "n_predict": MAX_TOKENS,
                "json_schema": self._json_schema,
            },
            timeout=REQUEST_TIMEOUT,
        )

        r.raise_for_status()

        content = r.json().get("content", "").strip()

        # llama-server wraps json_schema output in brackets
        if content.startswith("["):
            content = content[1:]
        if content.endswith("]"):
            content = content[:-1]
        content = content.strip()

        try:
            return json.loads(content)
        except Exception:
            logging.exception("Invalid classifier output")
            return {
                "needs_policy": False,
                "classifier_confidence": 0.0,
                "domains": [],
                "interaction_mode": "",
            }

    def shutdown(self):
        self.save_slot()

    def _health(self):
        r = self.session.get(f"{LLAMA_SERVER}/health", timeout=5)
        r.raise_for_status()

    def _prime_prompt(self):
        self.session.post(
            f"{LLAMA_SERVER}/completion",
            json={
                "prompt": CLASSIFIER_PROMPT,
                "slot_id": SLOT_ID,
                "cache_prompt": True,
                "stream": False,
                "n_predict": 1,
            },
            timeout=REQUEST_TIMEOUT,
        )
        PROMPT_HASH.write_text(
            hashlib.sha256(CLASSIFIER_PROMPT.encode()).hexdigest()
        )

    def _prompt_changed(self):
        current = hashlib.sha256(CLASSIFIER_PROMPT.encode()).hexdigest()
        if not PROMPT_HASH.exists():
            return True
        return PROMPT_HASH.read_text().strip() != current

    def save_slot(self):
        try:
            self.session.post(
                f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=save",
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            logging.exception("Slot save failed")

    def restore_slot(self):
        try:
            r = self.session.post(
                f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=restore",
                timeout=REQUEST_TIMEOUT,
            )
            return r.ok
        except Exception:
            return False

    def erase_slot(self):
        try:
            self.session.post(
                f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=erase",
                timeout=REQUEST_TIMEOUT,
            )
        except Exception:
            logging.exception("Slot erase failed")


engine = PreferencesEngine()
