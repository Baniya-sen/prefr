#!/usr/bin/env python3
"""
Test the classifier prompt against cloud LLMs through the Hermes-shaped
``ctx.llm.complete_structured()`` surface.

The classifier itself never imports ``adapter.py`` — it only calls
``ctx.llm.complete_structured(...)``. Here we build a local ``ctx`` via the
adapter so the exact same call can be exercised outside Hermes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from preferences_engine.adapter import make_ctx
from preferences_engine.prompt import CLASSIFIER_PROMPT


def load_schema() -> dict:
    path = Path(__file__).resolve().parent.parent / "schemas" / "CLASSIFY_SCHEMA.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def classify(
    ctx,
    message: str,
    schema: dict,
    provider: str | None = None,
    model: str | None = None,
) -> dict:
    """Run the classifier prompt via ctx.llm.complete_structured().

    This is the same call the real Hermes plugin will make — only the origin
    of ``ctx`` differs (here: adapter, there: Hermes).
    """
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

    print(f"  provider={result.provider} model={result.model} "
          f"content_type={result.content_type}")
    print(f"  tokens: in={result.usage.input_tokens} "
          f"out={result.usage.output_tokens} "
          f"cached={result.usage.cache_read_tokens}")

    if result.parsed is not None:
        return result.parsed

    print(f"  RAW: {result.text!r}")
    return {"needs_policy": False, "error": "parse_failed"}


def main() -> None:
    ctx = make_ctx()
    schema = load_schema()

    provider = sys.argv[1] if len(sys.argv) > 1 else None
    model = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"Provider: {provider or 'auto-detect'}, "
          f"Model: {model or 'auto-detect'}\n")

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
    ]

    if len(sys.argv) > 3:
        queries = [" ".join(sys.argv[3:])]

    for q in queries:
        print(f"Q: {q}")
        result = classify(ctx, q, schema, provider=provider, model=model)
        needs = result.get("needs_policy", False)
        status = "✅" if needs else "❌"
        print(f"  {status} needs_policy={needs} "
              f"| domains={result.get('domains', [])} "
              f"| mode={result.get('interaction_mode', '')} "
              f"| conf={result.get('classifier_confidence', 0.0)}")
        print()


if __name__ == "__main__":
    main()
