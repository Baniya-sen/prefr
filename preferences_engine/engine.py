"""
engine.py - Preferences Engine Runtime (V1)

Simple singleton runtime for a local llama-server classifier.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from typing import Any

from preferences_engine.config import (
    LOG_FILE,
    MAX_TOKENS,
    PROMPT_HASH,
    REQUEST_TIMEOUT,
    SCHEMA_NAME,
    SCHEMA,
    TEMPERATURE,
    PURPOSE
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

        self.started = False
        self._load_schema()
        self._load_classifier_prompt()

    def _load_schema(self) -> None:
        with open(SCHEMA, "r", encoding="utf-8") as f:
            self._json_schema = json.load(f)

    def _load_classifier_prompt(self) -> None:
        self._classifier_prompt = CLASSIFIER_PROMPT

    def start(self):
        # self._health()
        #
        # if self._prompt_changed():
        #     self.erase_slot()
        #
        # if not self.restore_slot():
        #     self._prime_prompt()
        #     self.save_slot()

        self.started = True
        logging.info("Preferences Engine ready")

    def llm_completion(
            self,
            *, ctx: Any,
            user_message: str,
            classifier_provider: str | None = None,
            classifier_model: str | None = None,
            **kwargs
    ) -> dict:
        if not self.started:
            self.start()

        return ctx.llm.complete_structured(
            schema_name=SCHEMA_NAME,
            system_prompt=self._classifier_prompt,
            json_schema=self._json_schema,
            json_mode=self._json_schema is not None,
            input=[{"type": "text", "text": user_message}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            purpose=PURPOSE,
            provider=classifier_provider,
            model=classifier_model,
            timeout=REQUEST_TIMEOUT
        )

    # def shutdown(self):
    #     self.save_slot()

    # def _health(self):
    #     r = self.session.get(f"{LLAMA_SERVER}/health", timeout=5)
    #     r.raise_for_status()

    def _prime_prompt(self):
        PROMPT_HASH.write_text(
            hashlib.sha256(self._classifier_prompt.encode()).hexdigest()
        )

    def _prompt_changed(self):
        current = hashlib.sha256(self._classifier_prompt.encode()).hexdigest()
        if not PROMPT_HASH.exists():
            return True
        return PROMPT_HASH.read_text().strip() != current

    # def save_slot(self):
    #     try:
    #         self.session.post(
    #             f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=save",
    #             timeout=REQUEST_TIMEOUT,
    #         )
    #     except Exception:
    #         logging.exception("Slot save failed")
    #
    # def restore_slot(self):
    #     try:
    #         r = self.session.post(
    #             f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=restore",
    #             timeout=REQUEST_TIMEOUT,
    #         )
    #         return r.ok
    #     except Exception:
    #         return False
    #
    # def erase_slot(self):
    #     try:
    #         self.session.post(
    #             f"{LLAMA_SERVER}/slots/{SLOT_ID}?action=erase",
    #             timeout=REQUEST_TIMEOUT,
    #         )
    #     except Exception:
    #         logging.exception("Slot erase failed")
