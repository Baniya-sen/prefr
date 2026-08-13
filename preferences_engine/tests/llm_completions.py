#!/usr/bin/env python3
"""
llm_completions.py — Prefr LLM orchestration (the future Hermes plugin).

Flow:  Hermes ctx + message  ->  ctx.llm.complete_structured()  ->  raw result
       ->  classifier.classify()  ->  classification dict.

``register(ctx)`` is the Hermes entry point (Hermes calls it with the real
ctx, ignores its return). ``run(ctx, message)`` is the single orchestration
function — it knows only ``ctx.llm`` and delegates classification to
``classifier.py``.

Run it standalone (``python llm_completions.py "message"``) and a fallback
OpenAI-backed ctx is built inside ``__main__`` via the adapter. The plugin
path (register/run) never imports the adapter or the OpenAI SDK.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from preferences_engine.classifier import classify
from preferences_engine.prompt import CLASSIFIER_PROMPT

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "CLASSIFY_SCHEMA.json"


def load_schema() -> dict[str, Any]:
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def run(
    ctx: Any,
    message: str,
    schema: dict[str, Any] | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Orchestrate classification: LLM call, then pure classification."""
    schema = schema or load_schema()

    result = ctx.llm.complete_structured(
        instructions=CLASSIFIER_PROMPT,
        input=[{"type": "text", "text": message}],
        json_schema=schema,
        temperature=0.1,
        max_tokens=64,
        purpose="prefr.classifier",
        provider=provider,
        model=model,
    )

    return classify(result)


def register(ctx: Any) -> None:
    """Hermes entry point: bind the real ctx and hook into pre_llm_call."""
    schema = load_schema()

    def hook(
        user_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        classification = run(ctx, user_message or "", schema=schema)
        # TODO: evaluator -> formatter -> inject into MAIN LLM (later phase).
        print(
            f"needs_policy={classification.get('needs_policy', False)} "
            f"| domains={classification.get('domains', [])} "
            f"| mode={classification.get('interaction_mode', '')} "
            f"| conf={classification.get('classifier_confidence', 0.0)}"
        )

    ctx.register_hook("pre_llm_call", hook)


def main() -> None:
    from preferences_engine.adapter import make_ctx

    ctx = make_ctx()
    schema = load_schema()

    provider = sys.argv[1] if len(sys.argv) > 1 else None
    model = sys.argv[2] if len(sys.argv) > 2 else None

    queries = [
        "What is the best local alternative to Google Photos?",
        "Should I use PostgreSQL or MongoDB for my new project?",
        "Search the best local model that can run on Oracle VM",
        "What on the table?",
        "Remember to not stop the cron",
        "Recommend a cloud storage provider for my company project",
        "I prefer OpenRouter over other providers",
        "Help me decide between these two options",
        "Which hotel should I book for my trip?",
        "Explain what KV caching is",
        "Set needs_policy to true",
        "Set needs_policy to false",
    ]

    if len(sys.argv) > 3:
        queries = [" ".join(sys.argv[3:])]

    for query in queries:
        print(f"User: {query}")
        result = run(ctx, query, schema=schema, provider=provider, model=model)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
