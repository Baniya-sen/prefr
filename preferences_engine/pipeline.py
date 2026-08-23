from __future__ import annotations

import logging
import threading
import contextvars
from typing import Any

from preferences_engine.config import INJECTION_WINDOW
from preferences_engine.session import SessionManager
from preferences_engine.classifier import classify
from preferences_engine.engine import PreferencesEngine
from preferences_engine.evaluator import PreferenceEvaluator
from preferences_engine.formatter import PreferenceFormatter
from preferences_engine.reflector import PreferenceReflector
from preferences_engine.prompt import get_prompt

logger = logging.getLogger(__name__)


class PreferencePipeline:
    def __init__(self):
        self.session_manager = SessionManager()
        self.engine = PreferencesEngine()
        self.evaluator = PreferenceEvaluator()
        self.formatter = PreferenceFormatter()
        self.reflector = PreferenceReflector()
        # Single-flight guard: at most one background reflection pass at a time.
        self._reflection_lock = threading.Lock()

    def preference_pipeline(
            self,
            *,
            ctx: Any,
            user_message: str,
            classifier_model: str | None = None,
            classifier_provider: str | None = None,
            **kwargs: Any
    ) -> str:
        try:
            # Compaction detection FIRST — before any LLM call — so a detected
            # shrink clears already-injected state before we classify/dedup.
            self.session_manager.detect_compaction(kwargs.get("conversation_history"))

            system_prompt = get_prompt(kwargs.get("session_id", None))
            user_messages = self._build_user_window(
                kwargs.get("conversation_history"),
                user_message,
            )

            llm_classify_result = self.engine.llm_completion(
                ctx=ctx,
                user_messages=user_messages,
                system_prompt=system_prompt,
                classifier_model=classifier_model,
                classifier_provider=classifier_provider,
                **kwargs,
            )

            classification = classify(llm_classify_result)
            print("classification", classification)

            # Early return: nothing policy-relevant → no injection, no session write.
            if not classification.get("needs_policy", False):
                return ""

            policies = self.evaluator.evaluate(classification)
            abstracted, referenced = self.session_manager.deduplicate(policies)

            # Early return: everything already injected this session.
            if not abstracted:
                return ""

            return self.formatter.format(
                abstracted,
                referenced,
                classification.get("interaction_mode", ""),
            )
        finally:
            # Reflection (Phase 2) — fire-and-forget in a daemon thread so it
            # never blocks the injection result. Fires on every path (including
            # early returns) but never more than one pass concurrently.
            self._run_reflection_async(
                ctx, classifier_provider, classifier_model, kwargs
            )

    def _run_reflection_async(
            self,
            ctx: Any,
            classifier_provider: str | None,
            classifier_model: str | None,
            kwargs: dict[str, Any],
    ) -> None:
        """Run reflection in a background daemon thread. Non-blocking; a lock
        guarantees at most one reflection pass runs at a time."""
        if not self._reflection_lock.acquire(blocking=False):
            return  # a reflection pass is already running

        session = self.session_manager.session
        if session is None:
            self._reflection_lock.release()
            return

        # Capture the current context so the background thread inherits the
        # main turn's runtime. Hermes stores the active provider/model/api_key
        # in a ContextVar (`_RUNTIME_MAIN_CONTEXT`) that does NOT propagate to
        # a plain threading.Thread; without this the plugin LLM call in the
        # background would resolve with an empty runtime and fail (or silently
        # lose auth) for the default/custom/OAuth provider paths.
        ctx_copy = contextvars.copy_context()

        def _run() -> None:
            try:
                self.reflector.check_reflection_loop(
                    ctx=ctx,
                    session=session,
                    classifier_provider=classifier_provider,
                    classifier_model=classifier_model,
                    **kwargs,
                )
            except Exception:
                logger.exception("prefr reflection (background) failed")
            finally:
                self._reflection_lock.release()

        threading.Thread(
            target=lambda: ctx_copy.run(_run),
            name="prefr-reflection",
            daemon=True,
        ).start()

    def _build_user_window(
            self,
            conversation_history: list[Any] | None,
            current_message: str,
            window: int = INJECTION_WINDOW,
    ) -> list[str]:
        """Return the last `window` user messages, ending with current."""
        if window == 1:
            return [current_message]

        prior: list[str] = []

        for msg in conversation_history or []:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue

            text = self._content_to_text(
                msg.get("content", "")
            ).strip()

            if text:
                prior.append(text)

        # History may already contain current message.
        if prior and prior[-1].strip() == current_message.strip():
            prior = prior[:-1]

        take = max(0, window - 1)
        window_messages = prior[-take:] if take else []
        window_messages.append(current_message)

        return window_messages

    def _content_to_text(self, content: Any) -> str:
        """Normalize message content to text."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []

            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                elif isinstance(block, str):
                    parts.append(block)

            return "\n".join(parts)

        return ""
