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
from functools import partial

from preferences_engine.session import SessionManager
from preferences_engine.pipeline import PreferencePipeline


def register(ctx: Any) -> None:
    session_manager = SessionManager()
    pipeline = PreferencePipeline()

    ctx.register_hook("on_session_start", partial(on_session_start, session_manager))
    ctx.register_hook("on_session_end", partial(on_session_end, session_manager))
    ctx.register_hook("on_session_finalize", partial(on_session_finalize, session_manager))
    ctx.register_hook("on_session_reset", partial(on_session_reset, session_manager))
    ctx.register_hook("pre_llm_call", partial(pre_llm_call, ctx, pipeline))


def on_session_start(
        session_manager: SessionManager,
        session_id: str,
        model: str,
        platform: str,
        **kwargs
) -> None:
    session_manager.start_session(session_id, model, platform, **kwargs)


def on_session_end(
        session_manager: SessionManager,
        session_id: str,
        completed: bool,
        interrupted: bool,
        model: str,
        platform: str,
        **kwargs
) -> None:
    session_manager.end_session(session_id, completed, interrupted, model, platform, **kwargs)


def on_session_finalize(
        session_manager: SessionManager,
        session_id: str | None,
        platform: str, **kwargs
) -> None:
    session_manager.finalize_session(session_id, platform, **kwargs)


def on_session_reset(
        session_manager: SessionManager,
        session_id: str,
        platform: str,
        **kwargs
) -> None:
    session_manager.reset_session(session_id, platform, **kwargs)


def pre_llm_call(
        ctx: Any,
        pipeline: PreferencePipeline,
        user_message: str | None = None,
        **kwargs: Any
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
