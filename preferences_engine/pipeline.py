from typing import Any

from preferences_engine.classifier import classify
from preferences_engine.engine import PreferencesEngine
from preferences_engine.evaluator import PreferenceEvaluator
from preferences_engine.formatter import PreferenceFormatter


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
            classifier_model: str | None = None,
            classifier_provider: str | None = None,
            **kwargs: Any
    ) -> str:
        llm_classify_result = self.engine.llm_completion(
            ctx=ctx,
            user_message=user_message,
            classifier_model=classifier_model,
            classifier_provider=classifier_provider,
            **kwargs,
        )

        classification = classify(llm_classify_result)
        policies = self.evaluator.evaluate(classification)
        injection = self.formatter.format(policies)

        return injection if isinstance(injection, str) else ""
