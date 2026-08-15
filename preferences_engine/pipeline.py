from __future__ import annotations

from typing import Any

from preferences_engine.classifier import classify
from preferences_engine.config import INJECTION_WINDOW
from preferences_engine.engine import PreferencesEngine
from preferences_engine.evaluator import PreferenceEvaluator
from preferences_engine.formatter import PreferenceFormatter
from preferences_engine.prompt import get_prompt


class PreferencePipeline:
    def __init__(self):
        self.engine = PreferencesEngine()
        self.evaluator = PreferenceEvaluator()
        self.formatter = PreferenceFormatter()

    def preference_pipeline(
            self,
            *,
            ctx: Any,
            user_message: str,
            session_id: str | None = None,
            classifier_model: str | None = None,
            classifier_provider: str | None = None,
            **kwargs: Any
    ) -> str:
        system_prompt = get_prompt(session_id)
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
        policies = self.evaluator.evaluate(classification)
        injection = self.formatter.format(policies)

        return injection if isinstance(injection, str) else ""

    def _build_user_window(
            self,
            conversation_history: list[Any] | None,
            current_message: str,
            window: int = INJECTION_WINDOW,
    ) -> list[str]:
        """Return the last `window` user messages, ending with current."""
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
