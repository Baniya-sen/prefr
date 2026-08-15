from typing import Any

from preferences_engine.classifier import classify
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

        llm_classify_result = self.engine.llm_completion(
            ctx=ctx,
            user_message=user_message,
            system_prompt=system_prompt,
            classifier_model=classifier_model,
            classifier_provider=classifier_provider,
            **kwargs,
        )

        classification = classify(llm_classify_result)
        policies = self.evaluator.evaluate(classification)
        injection = self.formatter.format(policies)

        return injection if isinstance(injection, str) else ""
