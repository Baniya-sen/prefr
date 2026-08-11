#!/usr/bin/env python3
"""Test the full preference engine pipeline: classify -> evaluate -> format."""

import sys

from preferences_engine.classifier import classify
from preferences_engine.evaluator import evaluator
from preferences_engine.formatter import formatter


def run_pipeline(query: str) -> None:
    print(f"Q: {query}")
    print("-" * 60)

    # Step 1: Classify
    classification = classify(query)
    print(f"Classification: {classification}")

    if not classification.get("needs_policy", False):
        print("No policies needed. Done.\n")
        return

    # Step 2: Evaluate
    policies = evaluator.evaluate(classification)
    print(f"Matched policies: {len(policies)}")
    for p in policies:
        print(f"  [{p.get('weight', '?')}] {p['id']} (score: {p.get('score', '?')})")

    # Step 3: Format for injection
    injection = formatter.format(policies)
    print(f"\nInjection block:\n{injection}\n")


if __name__ == "__main__":
    queries = [
        "What's the best local alternative to Google Photos?",
        "Should I use PostgreSQL or MongoDB for my new project?",
        "Search the best local model that can run on Oracle VM",
        "What on the table?",
        "Remember to not stop the cron",
        "Recommend a cloud storage provider for my company project",
    ]

    if len(sys.argv) > 1:
        queries = [" ".join(sys.argv[1:])]

    for q in queries:
        run_pipeline(q)
