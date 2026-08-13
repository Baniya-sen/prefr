"""
adapter.py — Local test adapter mimicking Hermes' plugin LLM access.

TEMPORARY. Delete this file before shipping to production.

Hermes hands each plugin a ``ctx`` whose ``.llm`` property exposes
``complete()`` and ``complete_structured()`` (see ``agent/plugin_llm.py``).
This module reproduces that exact surface locally, backed by the OpenAI
SDK against OpenRouter / OpenCode Go, so the classifier can be exercised
outside Hermes.

In production Hermes supplies the real ``ctx`` — the classifier never
imports this module, so deleting it changes nothing.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys

from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Data classes — mirror agent/plugin_llm.py:77-155
# ---------------------------------------------------------------------------


@dataclass
class PluginLlmTextInput:
    text: str
    type: str = "text"


@dataclass
class PluginLlmImageInput:
    data: Optional[bytes] = None
    url: Optional[str] = None
    mime_type: str = "image/png"
    file_name: str = ""
    type: str = "image"


PluginLlmInput = Union[PluginLlmTextInput, PluginLlmImageInput, Dict[str, Any]]


@dataclass
class PluginLlmUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: Optional[float] = None


@dataclass
class PluginLlmCompleteResult:
    text: str
    provider: str
    model: str
    agent_id: str
    usage: PluginLlmUsage = field(default_factory=PluginLlmUsage)
    audit: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginLlmStructuredResult:
    text: str
    provider: str
    model: str
    agent_id: str
    usage: PluginLlmUsage = field(default_factory=PluginLlmUsage)
    parsed: Optional[Any] = None
    content_type: str = "text"
    audit: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Provider config — local adapter only
# ---------------------------------------------------------------------------

PROVIDERS = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "default_model": "google/gemini-2.5-flash-lite",
    },
    "opencode-go": {
        "base_url": "https://opencode.ai/zen/go/v1",
        "env_key": "OPENCODE_GO_API_KEY",
        "model_env": "OPENCODE_GO_MODEL",
        "default_model": "deepseek-v4-flash",
    },
}


def _resolve_provider(provider: Optional[str]) -> str:
    """Pick provider: explicit arg wins, else first key present in env."""
    load_dotenv()

    if provider:
        return provider
    for name, cfg in PROVIDERS.items():
        if os.environ.get(cfg["env_key"]):
            return name
    raise RuntimeError(
        "Set OPENROUTER_API_KEY or OPENCODE_GO_API_KEY (or pass provider=...)"
    )


# ---------------------------------------------------------------------------
# PluginLlm — local OpenAI-backed implementation of the Hermes facade
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)```", re.DOTALL | re.IGNORECASE)


class PluginLlm:
    """Local stand-in for ``agent.plugin_llm.PluginLlm``.

    Backed by the OpenAI SDK instead of Hermes' auxiliary client. Exposes the
    same ``complete()`` / ``complete_structured()`` signatures and return
    types so consuming code is identical in both contexts.
    """

    def __init__(
        self,
        *,
        plugin_id: str = "prefr",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._plugin_id = plugin_id
        # Lazy: resolved at call time, exactly like Hermes (which resolves
        # provider/model inside complete()/complete_structured()).
        self._provider = provider
        self._default_model = model
        self._client: Optional[OpenAI] = None
        self._client_provider: Optional[str] = None

    def _resolve_provider(self, provider: Optional[str]) -> str:
        return provider or self._provider or _resolve_provider(None)

    def _resolve_model(self, provider: str, model: Optional[str]) -> str:
        load_dotenv()

        if model or self._default_model:
            return model or self._default_model
        cfg = PROVIDERS[provider]
        return os.environ.get(cfg["model_env"], cfg["default_model"])

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            provider = self._resolve_provider(None)
            cfg = PROVIDERS[provider]
            self._client = OpenAI(
                api_key=os.environ.get(cfg["env_key"], ""),
                base_url=cfg["base_url"],
                max_retries=0,
            )
            self._client_provider = provider
        return self._client

    # -- helpers ------------------------------------------------------------

    def _build_extra_body(self, provider: str) -> dict:
        """Provider-specific reasoning/thinking control (adapter's concern)."""
        extra: Dict[str, Any] = {}
        if provider == "openrouter":
            extra["reasoning"] = {"effort": "none"}
        elif provider == "opencode-go":
            extra["thinking"] = {"type": "disabled"}
        return extra

    def _extract_usage(self, response: Any) -> PluginLlmUsage:
        usage = PluginLlmUsage()
        raw = getattr(response, "usage", None)
        if raw is None:
            return usage
        usage.input_tokens = getattr(raw, "prompt_tokens", 0) or 0
        usage.output_tokens = getattr(raw, "completion_tokens", 0) or 0
        usage.total_tokens = getattr(raw, "total_tokens", 0) or 0
        details = getattr(raw, "prompt_tokens_details", None)
        if details is not None:
            usage.cache_read_tokens = getattr(details, "cached_tokens", 0) or 0
            usage.cache_write_tokens = getattr(details, "cache_write_tokens", 0) or 0
        return usage

    def _extract_text(self, response: Any) -> str:
        choice = response.choices[0] if response.choices else None
        return choice.message.content if choice and choice.message else ""

    # -- public API (mirror agent/plugin_llm.py) ----------------------------

    def complete(
        self,
        messages: List[Dict[str, Any]],
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        agent_id: Optional[str] = None,
        profile: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> PluginLlmCompleteResult:
        eff_provider = self._resolve_provider(provider)
        eff_model = self._resolve_model(eff_provider, model)
        kwargs: Dict[str, Any] = {"model": eff_model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        extra = self._build_extra_body(eff_provider)
        if extra:
            kwargs["extra_body"] = extra
        response = self.client.chat.completions.create(**kwargs)
        return PluginLlmCompleteResult(
            text=self._extract_text(response),
            provider=eff_provider,
            model=eff_model,
            agent_id=agent_id or "default",
            usage=self._extract_usage(response),
            audit={"plugin_id": self._plugin_id, "purpose": purpose or ""},
        )

    def complete_structured(
        self,
        *,
        instructions: str,
        input: Sequence[PluginLlmInput],
        json_schema: Optional[Any] = None,
        json_mode: bool = False,
        schema_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        agent_id: Optional[str] = None,
        profile: Optional[str] = None,
        purpose: Optional[str] = None,
    ) -> PluginLlmStructuredResult:
        if not instructions or not instructions.strip():
            raise ValueError("complete_structured requires non-empty instructions")
        if not input:
            raise ValueError("complete_structured requires at least one input block")

        eff_provider = self._resolve_provider(provider)
        eff_model = self._resolve_model(eff_provider, model)

        messages = self._build_structured_messages(
            instructions=instructions,
            inputs=list(input),
            json_mode=json_mode,
            json_schema=json_schema,
            schema_name=schema_name,
            system_prompt=system_prompt,
        )
        extra = self._build_extra_body(eff_provider)
        extra["response_format"] = self._json_response_format(
            json_mode=json_mode, json_schema=json_schema
        )

        kwargs: Dict[str, Any] = {
            "model": eff_model,
            "messages": messages,
            "extra_body": extra,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        response = self.client.chat.completions.create(**kwargs)
        text = self._extract_text(response)
        parsed, content_type = self._parse_structured_text(
            text=text, json_mode=json_mode, json_schema=json_schema
        )
        return PluginLlmStructuredResult(
            text=text,
            provider=eff_provider,
            model=eff_model,
            agent_id=agent_id or "default",
            usage=self._extract_usage(response),
            parsed=parsed,
            content_type=content_type,
            audit={
                "plugin_id": self._plugin_id,
                "purpose": purpose or "",
                "schema_name": schema_name or "",
            },
        )

    # -- internals (mirror agent/plugin_llm.py) -----------------------------

    @staticmethod
    def _normalize_input_block(block: PluginLlmInput) -> Dict[str, Any]:
        if isinstance(block, PluginLlmTextInput):
            return {"type": "text", "text": block.text}
        if isinstance(block, PluginLlmImageInput):
            d: Dict[str, Any] = {
                "type": "image",
                "mime_type": block.mime_type,
                "file_name": block.file_name,
            }
            if block.data is not None:
                d["data"] = block.data
            if block.url:
                d["url"] = block.url
            return d
        if isinstance(block, dict):
            kind = block.get("type")
            if kind == "text":
                text = block.get("text")
                if not isinstance(text, str):
                    raise ValueError("text input block requires 'text' string")
                return {"type": "text", "text": text}
            if kind == "image":
                if "data" not in block and not block.get("url"):
                    raise ValueError("image input block requires 'data' bytes or 'url'")
                return {
                    "type": "image",
                    "data": block.get("data"),
                    "url": block.get("url"),
                    "mime_type": block.get("mime_type") or "image/png",
                    "file_name": block.get("file_name") or "",
                }
            raise ValueError(f"Unknown input block type: {kind!r}")
        raise ValueError(f"Unsupported input block: {type(block).__name__}")

    @classmethod
    def _build_structured_messages(
        cls,
        *,
        instructions: str,
        inputs: Sequence[PluginLlmInput],
        json_mode: bool,
        json_schema: Optional[Any],
        schema_name: Optional[str],
        system_prompt: Optional[str],
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        sys_parts: List[str] = []
        if system_prompt:
            sys_parts.append(system_prompt.strip())
        if json_mode or json_schema is not None:
            sys_parts.append(
                "Respond with a single JSON object that matches the requested shape. "
                "Do not include prose or markdown fences."
            )
        if sys_parts:
            messages.append({"role": "system", "content": "\n\n".join(sys_parts)})

        user_parts: List[Dict[str, Any]] = []
        header = instructions.strip()
        if schema_name:
            header = f"{header}\n\nSchema name: {schema_name}"
        if json_schema is not None:
            try:
                schema_text = json.dumps(json_schema, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                schema_text = str(json_schema)
            header = f"{header}\n\nJSON schema:\n{schema_text}"
        user_parts.append({"type": "text", "text": header})

        for block in inputs:
            norm = cls._normalize_input_block(block)
            if norm["type"] == "text":
                user_parts.append({"type": "text", "text": norm["text"]})
            elif norm["type"] == "image":
                if norm.get("url"):
                    user_parts.append(
                        {"type": "image_url", "image_url": {"url": norm["url"]}}
                    )
                else:
                    data = norm.get("data") or b""
                    if not isinstance(data, (bytes, bytearray)):
                        raise ValueError("image input 'data' must be bytes")
                    b64 = base64.b64encode(data).decode("ascii")
                    mime = norm.get("mime_type") or "image/png"
                    user_parts.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{b64}"},
                        }
                    )

        messages.append({"role": "user", "content": user_parts})
        return messages

    @staticmethod
    def _json_response_format(
        *, json_mode: bool, json_schema: Optional[Any]
    ) -> Optional[Dict[str, Any]]:
        if json_schema is not None:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "plugin_structured_output",
                    "schema": json_schema,
                    "strict": False,
                },
            }
        if json_mode:
            return {"type": "json_object"}
        return None

    @classmethod
    def _parse_structured_text(
        cls, *, text: str, json_mode: bool, json_schema: Optional[Any]
    ) -> tuple[Optional[Any], str]:
        if not (json_mode or json_schema is not None):
            return None, "text"
        if not text:
            return None, "text"
        m = _FENCE_RE.search(text)
        clean = m.group(1).strip() if m else text.strip()
        try:
            parsed = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            return None, "text"
        return parsed, "json"


# ---------------------------------------------------------------------------
# PluginContext — local stand-in for hermes_cli.plugins.PluginContext
# ---------------------------------------------------------------------------


class PluginContext:
    def __init__(self, *, plugin_id: str = "prefr") -> None:
        self._plugin_id = plugin_id
        self._llm: Optional[PluginLlm] = None
        self._hooks: Dict[str, List[Any]] = {}

    @property
    def llm(self) -> PluginLlm:
        if self._llm is None:
            self._llm = PluginLlm(plugin_id=self._plugin_id)
        return self._llm

    def register_hook(self, name: str, callback: Any) -> None:
        self._hooks.setdefault(name, []).append(callback)

    def run_hook(self, name: str, **kwargs: Any) -> Any:
        results = []

        for callback in self._hooks.get(name, []):
            result = callback(**kwargs)

            if result is not None:
                results.append(result)

        return results[-1] if results else None


def make_ctx(*, plugin_id: str = "prefr") -> PluginContext:
    return PluginContext(plugin_id=plugin_id)


def main() -> None:
    from prefr import register

    ctx = make_ctx()

    register(ctx)

    print("Prefr Hermes adapter ready.")
    print("Type /exit to quit.\n")

    while True:
        user_message = input("User: ")

        if user_message == "/exit":
            break

        result = ctx.run_hook(
            "pre_llm_call",
            user_message=user_message,
        )

        print("\nPrefr:")
        print(result)
        print()


if __name__ == "__main__":
    main()
