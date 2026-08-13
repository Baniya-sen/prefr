# Hermes Agent — Internal Findings

Technical deep-dive into Hermes Agent internals. Source-code verified, not speculation.

**Date:** 2026-08-12
**Version:** Hermes Agent v0.19.0 (2026.7.20)
**Source:** `~/.hermes/hermes-agent/`

---

## 1. LLM API Client Stack

### SDK Used

Hermes uses the **OpenAI Python SDK (v2.24.0)** as its primary HTTP client layer for ALL providers, with two exceptions.

```
Hermes Agent
  → openai Python SDK (v2.24.0) — API client
    → httpx (v0.28.1) — HTTP transport
      → Provider's API endpoint
```

### Provider Dispatch (`agent/chat_completion_helpers.py:413-457`)

| `api_mode` | Client Used | Notes |
|---|---|---|
| `codex_responses` | OpenAI SDK + Codex wrapper | OpenAI Responses API |
| `anthropic_messages` | `anthropic` Python SDK | Native Anthropic Messages API |
| `bedrock_converse` | boto3 | AWS Bedrock |
| Everything else | `openai.OpenAI(**kwargs)` | OpenRouter, OpenCode Go, Nous, xAI, Gemini, custom |

The actual client construction lives in `agent/agent_runtime_helpers.py:1966-2058`:
```python
def create_openai_client(agent, client_kwargs, *, reason, shared):
    # SSL, keepalives, proxy validation...
    client = _ra().OpenAI(**client_kwargs)  # ← OpenAI SDK constructor
    return client
```

The `client_kwargs` dict contains `api_key` and `base_url` resolved from config. For OpenCode Go, this means `OpenAI(api_key=..., base_url=http://127.0.0.1:8080/...)` with standard Chat Completions JSON over httpx.

---

## 2. KV Cache / Prompt Caching

### Architecture: System Prompt 3-Tier Split (`agent/system_prompt.py:152-168`)

The system prompt is assembled as three ordered cache tiers:

| Tier | Contents | Stability |
|---|---|---|
| `stable` | SOUL.md identity, tool guidance, task-completion rules | Cross-session identical |
| `context` | Workspace snapshot, project files, caller system_message | Per-session |
| `volatile` | Memory snapshot, user profile, timestamps | Per-turn |

These are joined into one string and cached on `agent._cached_system_prompt` for the **entire lifetime of the AIAgent** — never re-rendered mid-session. This is the core invariant:

> "Hermes never re-renders parts of this string mid-session — that's the only way to keep upstream prompt caches warm across turns."

### Anthropic Prompt Caching (`agent/prompt_caching.py`)

For Claude models on Anthropic/OpenRouter, Hermes injects **4 cache breakpoints** via `cache_control: {"type": "ephemeral"}`:

1. Static system prefix (stable tier) — cached independently
2. End of full system prompt
3. Last 2 non-system messages

The system prompt is split at the API level only:
```python
# prompt_caching.py:108-116
message["content"] = [
    {"type": "text", "text": static_system_prefix, "cache_control": {"type": "ephemeral", "ttl": "5m"}},
    {"type": "text", "text": suffix, "cache_control": {"type": "ephemeral", "ttl": "5m"}},
]
```

TTL configurable: `5m` (default) or `1h` via `config.yaml → prompt_caching.cache_ttl`.

### OpenAI Automatic Prefix Caching (All Other Providers)

No explicit `cache_control` markers. Relies on OpenAI's **automatic prefix matching** — provider silently reuses KV cache when prefix is byte-identical.

The mechanism: **`api_content` sidecar** (`agent/turn_context.py:87-95`, `conversation_loop.py:1383-1438`):

- When a user message is first sent, injected context (memory, plugins) is composed and stored as `api_content`
- On subsequent turns, historical messages are replayed with their **exact original `api_content` bytes**
- This ensures the provider sees the identical byte sequence it cached on the first turn

```python
# conversation_loop.py:1429-1438
# Historical message: replay the exact bytes sent when it was
# live, so the provider prompt-cache prefix stays byte-stable
api_msg["content"] = _api_content
```

### Codex/xAI: Content-Addressed `prompt_cache_key` (`agent/transports/codex.py:318-336`)

```python
cache_key = _content_cache_key(instructions, response_tools) or session_id
kwargs["prompt_cache_key"] = cache_key
```

Sent as body field + HTTP headers (`session_id`, `x-client-request-id`) for cache-scope routing.

### How Prefix Caching Works (Verified from Official Docs)

The API receives a **flat token sequence**, not "messages." Prefix matching happens from position 0:

```
Request 1:  [SP_tokens (1500)][Q1_tokens (10)]  = 1510 tokens → all new, SP cached
Request 2:  [SP_tokens (1500)][Q2_tokens (8)]   = 1508 tokens → first 1500 match, only 8 new
```

- **OpenAI**: "Cache hits are only possible for exact prefix matches within a prompt." Minimum 1024 tokens for caching to trigger. Routes requests based on hash of first ~256 tokens.
- **vLLM**: Hash-chaining at block level. If block N matches, blocks 0..N-1 are guaranteed identical.
- **GPT-5.6+**: Uses implicit breakpoints at latest user message. Explicit `prompt_cache_breakpoint` recommended for stable prefixes.

---

## 3. Session ID in API Calls

| Provider | Session ID Sent? | Where? |
|---|---|---|
| OpenAI direct | ❌ No | — |
| OpenRouter (non-Grok) | ❌ No | — |
| OpenRouter (Grok) | ✅ Yes | `x-grok-conv-id` header |
| OpenCode Go | ❌ No | — |
| Codex backend | ✅ Yes | `session_id` + `x-client-request-id` headers, `prompt_cache_key` body |
| xAI direct | ✅ Yes | `x-grok-conv-id` header |

Hermes only sends session IDs to providers that actively use them for cache routing. For standard OpenAI-compatible APIs, it relies purely on prefix matching.

---

## 4. Plugin LLM API (`ctx.llm.complete()`)

### It's a Raw API Call — Clean Slate

`ctx.llm.complete()` does **NOT** go through Hermes's conversation loop. It does NOT include:
- ❌ Hermes's system prompt
- ❌ Tool definitions
- ❌ Conversation history
- ❌ Memory/context injections
- ❌ Any prompt-cache decoration

It's a direct `client.chat.completions.create()` call using the same OpenAI SDK client.

Call chain:
```
ctx.llm.complete(messages=[...])
  → plugin_llm._invoke_sync()
    → auxiliary_client.call_llm()
      → _get_cached_client()  ← OpenAI SDK client for the provider
      → client.chat.completions.create(messages=your_messages, ...)
```

### Parameters

```python
result = ctx.llm.complete(
    messages=[                          # REQUIRED — standard OpenAI messages
        {"role": "system", "content": "You are a classifier."},
        {"role": "user", "content": "Classify: " + text}
    ],
    provider="openrouter",             # optional — override provider
    model="anthropic/claude-sonnet-4", # optional — override model
    temperature=0.2,                   # optional
    max_tokens=512,                    # optional
    timeout=30,                        # optional — seconds
    purpose="memory.classifier",       # optional — logging tag only
)

# result.text      = raw string response
# result.provider  = which provider handled it
# result.model     = which model handled it
# result.usage     = token counts
```

Structured output:
```python
result = ctx.llm.complete_structured(
    instructions="Classify this memory",
    input=[{"type": "text", "text": user_message}],
    json_schema={...},
    temperature=0.0,
    max_tokens=128,
)
# result.parsed = Python dict (already validated)
```

Async variants: `ctx.llm.acomplete(...)`, `ctx.llm.acomplete_structured(...)`

### Model Override — Gated by Trust Policy

Overrides are **denied by default**. Must be explicitly allowed in config.yaml:

```yaml
plugins:
  entries:
    my-plugin:
      llm:
        allow_provider_override: true    # default: false
        allow_model_override: true       # default: false
        allowed_providers: ["openrouter", "opencode-go"]  # optional allowlist
        allowed_models: ["anthropic/claude-sonnet-4"]      # optional allowlist
```

Resolution priority (`auxiliary_client.py:6570-6576`):
1. Explicit args (`provider=`, `model=`) — always win
2. Config file (`auxiliary.<task>.provider/model`) — if `task=` is passed
3. `"auto"` — fallback to main model

### Plugins Reading Config

Plugins import config directly — it's a public API:

```python
from hermes_cli.config import load_config

config = load_config()
aux_config = config.get("auxiliary", {})
vision_model = aux_config.get("vision", {}).get("model", "")
```

### Key Source Files

| File | Purpose |
|---|---|
| `agent/plugin_llm.py` | PluginLlm facade — complete(), complete_structured() |
| `agent/auxiliary_client.py` | call_llm() — centralized LLM call with provider resolution |
| `agent/agent_runtime_helpers.py` | create_openai_client() — SDK client construction |
| `agent/chat_completion_helpers.py` | _dispatch_api_call() — provider routing |
| `agent/prompt_caching.py` | Anthropic cache_control marker injection |
| `agent/turn_context.py` | api_content sidecar — byte-stable replay |
| `agent/system_prompt.py` | 3-tier system prompt assembly |
| `agent/transports/codex.py` | Codex/xAI cache-scope headers |
| `hermes_cli/plugins.py` | PluginContext class — ctx.llm, ctx.subagent_lifecycle |
| `hermes_cli/config.py` | DEFAULT_CONFIG, load_config() |

---

## 5. Warm System Prompt Pattern (Independent Queries)

For stateless independent queries with a warm SP prefix:

```python
from openai import OpenAI

SYSTEM_PROMPT = """Your long system prompt here..."""  # 1024+ tokens

client = OpenAI(api_key="...", base_url="...")

# Every request: [SP, query] — same prefix = KV cache hit
response = client.chat.completions.create(
    model="your-model",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},  # same every time
        {"role": "user", "content": "Your query"},      # changes
    ]
)
```

Key requirements:
- SP must be **1024+ tokens** (~4000+ chars) for OpenAI/Anthropic caching
- SP must be **byte-identical** across requests (no dynamic content)
- Provider must support prefix caching (OpenAI, Anthropic, vLLM do)
- No server-side session — every request must be self-contained

See `~/Personal/warm-sp.py` for working implementation.

---

## 6. Config Reference

### Key Config Paths

| Path | Purpose |
|---|---|
| `model.provider` | Main LLM provider |
| `model.model` | Main model name |
| `model.base_url` | Custom endpoint URL |
| `prompt_caching.cache_ttl` | `"5m"` or `"1h"` — Anthropic cache TTL |
| `auxiliary.vision.provider/model` | Vision task model |
| `auxiliary.compression.provider/model` | Context compression model |
| `auxiliary.web_extract.provider/model` | Web extraction model |
| `plugins.entries.<id>.llm.*` | Plugin LLM trust policy |

### Config Access

```python
# Official API — works from plugins, scripts, anywhere
from hermes_cli.config import load_config
config = load_config()
```

---

## 7. Temperature Handling

Hermes does **NOT** send a default temperature. It's omitted unless explicitly set.

### Logic (`transports/chat_completions.py:541-550`)

```python
# Profile path:
if profile.fixed_temperature is OMIT_TEMPERATURE:
    pass  # Don't include temperature at all
elif profile.fixed_temperature is not None:
    api_kwargs["temperature"] = profile.fixed_temperature
else:
    temp = params.get("temperature")
    if temp is not None:
        api_kwargs["temperature"] = temp
```

**Default:** Temperature not sent — provider uses server-side default.

**Model-specific overrides:**
- Kimi/Moonshot → `OMIT_TEMPERATURE` (server-managed, never sent)
- Opus 4.7+ → temperature stripped (rejects non-default values)
- Other models → only sent if explicitly configured

---

## 8. Reasoning (Thinking/CoT) Control

Per-provider wire formats — **not uniform across providers**.

### OpenRouter

Sent as `extra_body.reasoning` (Python SDK) or top-level `reasoning` (TypeScript/REST):

```python
# Python SDK — MUST be in extra_body
extra_body={"reasoning": {"enabled": False}}

# To disable: effort "none"
extra_body={"reasoning": {"effort": "none"}}

# To set level
extra_body={"reasoning": {"effort": "high"}}  # low|medium|high|xhigh|max
```

**Python SDK constraint:** OpenAI SDK 2.24.0 has no `**kwargs` on `create()`. Passing `reasoning` as top-level kwarg raises `TypeError`. Must go in `extra_body`.

### OpenCode Go (per-model)

| Model | Disable | Set Effort |
|---|---|---|
| GLM-5.2 | Don't send `reasoning_effort` | `reasoning_effort: "high"` or `"max"` (top-level) |
| Kimi K2 | `extra_body.thinking.type: "disabled"` | `reasoning_effort: "low"/"medium"/"high"` (top-level) |
| DeepSeek thinking (v4-pro, reasoner) | `extra_body.thinking.type: "disabled"` | `reasoning_effort: "low"/"medium"/"high"` (top-level) |
| Other (deepseek-v4-flash, glm-5, etc.) | No API control | No API control |

Source: `plugins/model-providers/opencode-zen/__init__.py:40-127`

### Kimi/Moonshot (direct)

```python
extra_body={"thinking": {"type": "disabled"}}  # or "enabled"
# mutually exclusive with reasoning_effort — never both
```

### Anthropic (native Messages API)

Reasoning is controlled via `thinking` parameter in the Messages API wire format, not via `extra_body`. Handled by `agent/anthropic_adapter.py`.

### Summary

| Provider | Disable Reasoning | Wire Location |
|---|---|---|
| OpenRouter | `reasoning.effort: "none"` or `reasoning.enabled: false` | `extra_body` (Python) |
| OpenCode Go (DeepSeek/Kimi) | `thinking.type: "disabled"` | `extra_body` |
| OpenCode Go (GLM-5.2) | Omit `reasoning_effort` | top-level |
| Kimi direct | `thinking.type: "disabled"` | `extra_body` |
| LM Studio | Omit `reasoning_effort` | top-level |

---

## 9. `ctx.llm.complete_structured()` Interface

Different from raw `client.chat.completions.create()` — not a drop-in replacement.

### Parameters

```python
result = ctx.llm.complete_structured(
    instructions="Classify this memory",     # replaces system message
    input=[{"type": "text", "text": query}], # replaces user message
    json_schema={...},                        # JSON Schema for validation
    temperature=0.0,
    max_tokens=128,
    model="deepseek-v4-flash",               # optional — override model
    provider="opencode-go",                  # optional — override provider
    purpose="memory.classifier",             # logging tag only
)
# result.parsed = validated Python dict
# result.text = raw JSON string
```

### What You Lose vs Raw SDK

- `extra_body` — no way to pass `reasoning`, `session_id`, or provider-specific fields
- Direct provider/model control — resolved from config unless overridden
- `response_format` — handled differently via `json_schema` param
- Fine-grained control over request shape

### When to Use

- Quick classification/summarization inside a plugin
- When you don't need provider-specific knobs
- When Hermes's auth/retry/fallback is useful

### When NOT to Use

- When you need `extra_body` (reasoning control, session_id)
- When you need direct provider/model selection
- When you need `response_format` with custom JSON Schema

---

## 10. Custom Plugin Config

`load_config()` reads the full YAML — no schema validation, no rejection of unknown keys.

### config.yaml

```yaml
plugins:
  entries:
    my-classifier:
      llm:
        allow_provider_override: true
        allow_model_override: true
      # Custom config — Hermes ignores it, your plugin reads it
      classifier:
        sp_length_min: 1024
        default_temperature: 0.1
        cache_warmup_query: ""
```

### Plugin Code

```python
from hermes_cli.config import load_config

config = load_config()
my_cfg = config.get("plugins", {}). get("entries", {}).get("my-classifier", {})
classifier_cfg = my_cfg.get("classifier", {})

temp = classifier_cfg.get("default_temperature", 0.1)
```

Hermes only reads the keys it knows (`llm.allow_*`, etc.). Everything else is invisible to it — your plugin reads it directly via `load_config()`.

---

## 11. `extra_body` vs Top-Level Parameters

**Python SDK (OpenAI 2.24.0):** No `**kwargs` on `create()`. Unknown parameters raise `TypeError`.

| Parameter | Where to Put It | Why |
|---|---|---|
| `reasoning` | `extra_body` | Not a recognized SDK parameter |
| `thinking` | `extra_body` | Not a recognized SDK parameter |
| `session_id` | `extra_body` | Not a recognized SDK parameter |
| `response_format` | Top-level | Recognized SDK parameter |
| `temperature` | Top-level | Recognized SDK parameter |
| `max_tokens` | Top-level | Recognized SDK parameter |
| `model` | Top-level | Recognized SDK parameter |
| `messages` | Top-level | Recognized SDK parameter |

OpenRouter forwards all `extra_body` fields to the upstream provider. OpenCode Go (vLLM) also accepts them.

---

*Source-verified against Hermes Agent v0.19.0 codebase at `~/.hermes/hermes-agent/` and OpenRouter official docs.*
