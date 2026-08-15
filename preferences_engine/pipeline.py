from __future__ import annotations

from typing import Any

from preferences_engine.classifier import classify
from preferences_engine.config import INJECTION_WINDOW
from preferences_engine.engine import PreferencesEngine
from preferences_engine.evaluator import PreferenceEvaluator
from preferences_engine.formatter import PreferenceFormatter
from preferences_engine.prompt import get_prompt


def _content_to_text(content: Any) -> str:
    """Normalize an OpenAI-style message content (str or list of blocks) to text."""
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


def build_user_window(
        conversation_history: list[Any] | None,
        current_message: str,
        window: int = INJECTION_WINDOW,
) -> list[str]:
    """Return the last `window` user messages, ending with the current one.

    Prior messages are context for resolving references ("the second one"); the
    final element is always the current message — the classification target.
    """
    prior: list[str] = []
    for msg in conversation_history or []:
        if not isinstance(msg, dict) or msg.get("role") != "user":
            continue
        text = _content_to_text(msg.get("content", "")).strip()
        if text:
            prior.append(text)

    # History may already include the current message as the last user turn.
    if prior and prior[-1].strip() == current_message.strip():
        prior = prior[:-1]

    take = max(0, window - 1)
    window_messages = prior[-take:] if take else []
    window_messages.append(current_message)
    return window_messages


class PreferencePipeline:
    def __init__(self):
        self.engine = PreferencesEngine()
        self.evaluator = PreferenceEvaluator()
        self.formatter = PreferenceFormatter()

    def preference_pipeline(
            self,
            *,
            ctx: Any,
            user_messages: list[str],
            session_id: str | None = None,
            classifier_model: str | None = None,
            classifier_provider: str | None = None,
            **kwargs: Any
    ) -> str:
        system_prompt = get_prompt(session_id)

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
