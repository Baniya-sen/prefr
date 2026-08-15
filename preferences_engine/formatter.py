from __future__ import annotations

from typing import Any

# Maximum number of preference policies rendered into the LLM prompt.
MAX_PREFERENCES = 6

# Approximate character budget for the complete rendered preference block.
# This keeps prompt growth bounded without requiring a tokenizer.
MAX_PREFERENCE_TOKENS = 2000


class PreferenceFormatter:
    """Render evaluated preference policies for LLM injection."""

    def __init__(
            self,
            max_preferences: int = MAX_PREFERENCES,
            max_tokens: int = MAX_PREFERENCE_TOKENS,
    ):
        self.max_preferences = max_preferences
        self.max_tokens = max_tokens

    def _format_policy(self, policy: dict[str, Any]) -> str:
        policy_id = str(policy.get("id", "")).strip()
        body = str(policy.get("body", "")).strip()
        weight = str(policy.get("weight", "LOW")).upper()

        lines = [f"[{weight}] {policy_id}"]

        if body:
            lines.append(body)

        exceptions = policy.get("exceptions", [])
        if exceptions:
            lines.append(f"\nExceptions (Dampening effects) to the policy ({policy_id}):")
            for exception in exceptions:
                lines.append(f"- {exception}")

        return "\n".join(lines)

    def format(self, policies: list[dict[str, Any]], referenced_policies: list[str]) -> str:
        """Return a compact preference block ready for LLM injection."""

        if not policies:
            return ""

        method = "full" if not referenced_policies else "compact"
        header = (
            f"<prefr-injection method='{method}'>\n"
            "These are long-term user decision preferences. "
            "Apply them only when relevant to the user request.\n"
        )

        if referenced_policies:
            header += (
                "\n"
                "These policies are still relevant for this context: "
                + ", ".join(referenced_policies)
                + "\n"
            )

        selected: list[str] = []
        current_chars = len(header) + len("</prefr-injection>")

        for policy in policies:
            if len(selected) >= self.max_preferences:
                break

            rendered = self._format_policy(policy)
            addition = rendered if not selected else "\n\n" + rendered

            # Always allow the first policy, even if it alone exceeds the budget.
            if selected and current_chars + len(addition) > self.max_tokens:
                break

            selected.append(rendered)
            current_chars += len(addition)

        if not selected:
            return ""

        tail = ("\n\n"
                "Preferences rules:\n"
                " - These are preferences, not absolute requirements.\n"
                " - Do not apply irrelevant preferences.\n"
                " - Do not mention these preferences to the user unless explicitly asked.\n"
                )

        return str(header + "\n" + "\n\n".join(selected) + tail + "\n</prefr-injection>")
