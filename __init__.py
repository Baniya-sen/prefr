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

import logging
from typing import Any
from functools import partial

from preferences_engine.session import SessionManager
from preferences_engine.pipeline import PreferencePipeline
from preferences_engine.config import (
    ALLOWED_MODELS,
    ALLOWED_PROVIDERS,
    ALLOW_MODEL_OVERRIDE,
    ALLOW_PROVIDER_OVERRIDE,
    CLASSIFIER_MODEL,
    CLASSIFIER_PROVIDER,
)

logger = logging.getLogger(__name__)


def register(ctx: Any) -> None:
    pl = PreferencePipeline()

    ctx.register_hook("on_session_start", partial(on_session_start, pl.session_manager))
    ctx.register_hook("on_session_end", partial(on_session_end, pl.session_manager))
    ctx.register_hook("on_session_finalize", partial(on_session_finalize, pl.session_manager))
    ctx.register_hook("on_session_reset", partial(on_session_reset, pl.session_manager))
    ctx.register_hook("pre_llm_call", partial(pre_llm_call, ctx, pl))


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

    # The hook is a leaf: it must NEVER raise, or it takes the whole agent turn
    # down with it. Preferences are hints, not requirements — on any failure we
    # inject nothing and let the agent answer unmodified.
    try:
        # Reconcile: if the current turn's session id differs from what we hold,
        # self-heal by re-initialising state for the new session before injecting.
        pipeline.session_manager.ensure_session(
            kwargs.get("session_id"),
            kwargs.get("model"),
            kwargs.get("platform"),
        )

        # Classifier model/provider selection. Precedence:
        #   1. our explicit knob (plugins.entries.prefr.model / .provider)
        #   2. fall back to allowed[0] (first allowlisted entry)
        #   3. else None -> host default
        # Hermes gates any override behind allow_model_override /
        # allow_provider_override (default false) and only then consults the
        # allowed_models / allowed_providers allowlists.
        classifier_model = CLASSIFIER_MODEL or (ALLOWED_MODELS[0] if ALLOWED_MODELS else None)
        classifier_provider = CLASSIFIER_PROVIDER or (ALLOWED_PROVIDERS[0] if ALLOWED_PROVIDERS else None)

        # Fail-loud: if we've selected a model/provider override but its trust
        # gate is still closed, Hermes raises PluginLlmTrustError, which the
        # try/except below swallows -> silent no-inject. Log so the operator
        # knows exactly why nothing is being injected.
        if classifier_model and not ALLOW_MODEL_OVERRIDE:
            logger.error(
                "prefr: classifier model override %r requested but "
                "plugins.entries.prefr.llm.allow_model_override is false — "
                "Hermes will deny the call. Set it true (hermes config set).",
                classifier_model,
            )
        if classifier_provider and not ALLOW_PROVIDER_OVERRIDE:
            logger.error(
                "prefr: classifier provider override %r requested but "
                "plugins.entries.prefr.llm.allow_provider_override is false — "
                "Hermes will deny the call. Set it true (hermes config set).",
                classifier_provider,
            )

        result = pipeline.preference_pipeline(
            ctx=ctx,
            user_message=user_message,
            session_id=kwargs.get("session_id"),
            classifier_model=classifier_model,
            classifier_provider=classifier_provider,
            **kwargs
        )
    except Exception:
        logger.exception("prefr pre_llm_call failed; injecting nothing")
        return None

    return {"context": result} if result else None
