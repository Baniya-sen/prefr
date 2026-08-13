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
            lines.append("Exceptions(Dampening effects) to this policy:")
            for exception in exceptions:
                lines.append(f"- {exception}")

        return "\n".join(lines)

    def format(self, policies: list[dict[str, Any]]) -> str:
        """Return a compact preference block ready for LLM injection."""

        if not policies:
            return ""

        header = (
            "<user-preferences>\n"
            "The following user preferences are derived from user preference policies. "
            "These may or may not be relevant:\n"
        )

        selected: list[str] = []
        current_chars = len(header) + len("</user-preferences>")

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

        return str(header + "\n" + "\n\n".join(selected) + "\n</user-preferences>")
