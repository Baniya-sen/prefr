#!/usr/bin/env python3
"""
Prefr LLM orchestration (Hermes plugin).

Flow:  Hermes ctx + message  ->  ctx.llm.complete_structured()  ->  raw result
       ->  classifier.classify()  ->  classification dict.

``register(ctx)`` is the Hermes entry point (Hermes calls it with the real
ctx, ignores its return). ``classify(ctx, message)`` is the orchestration
function — it knows only ``ctx.llm`` and delegates the classification logic
to ``classifier.py``.
"""

from __future__ import annotations

from typing import Any

from preferences_engine.pipeline import PreferencePipeline


def register(ctx: Any) -> None:
    pipeline = PreferencePipeline()

    def pre_llm_call(
        user_message: str | None = None,
        **kwargs: Any,
    ) -> dict[str, str] | None:
        if not user_message:
            return None

        classifier_model = None
        classifier_provider = None

        result = pipeline.preference_pipeline(
            ctx=ctx,
            user_message=user_message,
            classifier_model=classifier_model,
            classifier_provider=classifier_provider,
            **kwargs
        )

        return {"context": result} if result else None

    ctx.register_hook("pre_llm_call", pre_llm_call)
