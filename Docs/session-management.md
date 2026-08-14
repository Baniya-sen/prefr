# Prefr — Hermes Session Management (Plugin Hooks)

Source-verified against `hermes-agent` (docs + `agent/turn_finalizer.py`,
`agent/run_agent.py`, `hermes_cli/plugins.py`). For Prefr's session-management
wrapper.

---

## The 5 session hooks at a glance

| Hook | Fires when | Returns |
|------|-----------|---------|
| `on_session_start` | A brand-new session is created (first turn only) | ignored |
| `on_session_end` | Every `run_conversation()` call ends (every turn) | ignored |
| `on_session_finalize` | CLI/gateway tears down an active session (`/new`, GC, quit) | ignored |
| `on_session_reset` | Gateway swaps in a fresh session key (`/new`, `/reset`, `/clear`) | ignored |
| `pre_llm_call` | Once per turn, before the tool-calling loop | `{"context": str}` → inject into user message |

**Two critical distinctions** (they trip people up):

1. **`on_session_end` fires EVERY turn**, not just when the session ends.
   It's the per-turn cleanup point. The "end" name refers to the end of the
   `run_conversation()` call, not end-of-session.
2. **`on_session_finalize`** and **`on_session_reset`** are the actual
   "session is going away" signals. `finalize` = outgoing session is being
   torn down; `reset` = new session key has been swapped in.

**Gateway order on `/new` / `/reset`:**

```
on_session_finalize(old_id) → swap → on_session_reset(new_id) → on_session_start(new_id) [on next inbound turn]
```

---

## `register(ctx)` — how Prefr wires them

```python
def register(ctx):
    ctx.register_hook("on_session_start",   on_session_start)
    ctx.register_hook("on_session_end",     on_session_end)
    ctx.register_hook("on_session_finalize", on_session_finalize)
    ctx.register_hook("on_session_reset",   on_session_reset)
    ctx.register_hook("pre_llm_call",       pre_llm_call)
```

---

## `on_session_start`

Fires **once** on a brand-new session. Does **NOT** fire on continuation
(second message in the same session). The check is `if not conversation_history`.

```python
def on_session_start(session_id: str, model: str, platform: str, **kwargs) -> None:
    ...
```

| Param | Type | Meaning |
|-------|------|---------|
| `session_id` | `str` | new session id |
| `model` | `str` | active model |
| `platform` | `str` | `"telegram"`, `"cli"`, etc. |
| `**kwargs` | — | `task_id`, `turn_id`, `telemetry_schema_version`, more (forward-compat) |

**Returns:** ignored. **Use for:** init session-scoped state, warm caches, log start.

---

## `on_session_end`

Fires at the **end of every turn** (every `run_conversation()` call), regardless
of outcome. Also fires from the CLI atexit handler if the agent was mid-turn on exit
(then `completed=False`, `interrupted=True`).

```python
def on_session_end(
    session_id: str,
    completed: bool,
    interrupted: bool,
    model: str,
    platform: str,
    **kwargs,
) -> None:
    ...
```

| Param | Type | Meaning |
|-------|------|---------|
| `session_id` | `str` | session id |
| `completed` | `bool` | `True` if a final response was produced |
| `interrupted` | `bool` | `True` if `/stop`, new message, or quit cut the turn short |
| `model` | `str` | active model |
| `platform` | `str` | platform name |
| `**kwargs` | — | `task_id`, `turn_id`, `telemetry_schema_version`, more |

Source (verbatim kwargs from `agent/turn_finalizer.py:673-682`): `session_id`,
`task_id`, `turn_id`, `completed`, `interrupted`, `model`, `platform`.

**Returns:** ignored. **Use for:** flush buffers, persist state, duration logging.

> ⚠️ Name is misleading. This is the **per-turn** hook, not end-of-session. For
> "the session is gone", use `on_session_finalize` / `on_session_reset`.

---

## `on_session_finalize`

Fires when CLI/gateway **tears down an active session** — `/new`, idle-session GC,
or CLI quit with an active agent. Last chance to flush state tied to the *outgoing*
session before its identity is gone.

```python
def on_session_finalize(session_id: str | None, platform: str, **kwargs) -> None:
    ...
```

| Param | Type | Meaning |
|-------|------|---------|
| `session_id` | `str \| None` | outgoing session id; `None` if no active session |
| `platform` | `str` | `"cli"` or `"telegram"` etc. |
| `**kwargs` | — | forward-compat |

**Returns:** ignored. **Use for:** final metrics before the id is discarded, close
per-session resources, drain queued writes. Always paired with `on_session_reset`
on the gateway side.

---

## `on_session_reset`

Fires when the gateway **swaps in a new session key** for an active chat — `/new`,
`/reset`, `/clear`, or idle-session rotation. Conversation state has been wiped;
react without waiting for the next `on_session_start`.

```python
def on_session_reset(session_id: str, platform: str, **kwargs) -> None:
    ...
```

| Param | Type | Meaning |
|-------|------|---------|
| `session_id` | `str` | the NEW session id (already rotated) |
| `platform` | `str` | platform name |
| `**kwargs` | — | forward-compat |

**Returns:** ignored. **Use for:** reset per-session caches keyed by `session_id`,
"session rotated" analytics, prime a fresh state bucket.

---

## `pre_llm_call` (the one that returns something)

Fires **once per turn**, before the tool loop. The only session-adjacent hook whose
return value affects behavior.

```python
def pre_llm_call(
    session_id: str,
    user_message: str,
    conversation_history: list,
    is_first_turn: bool,
    model: str,
    platform: str,
    **kwargs,
) -> dict | str | None:
    ...
```

| Param | Type | Meaning |
|-------|------|---------|
| `session_id` | `str` | session id |
| `task_id` | `str` | effective task id |
| `turn_id` | `str` | current turn id |
| `user_message` | `str` | raw user message |
| `conversation_history` | `list` | message list |
| `is_first_turn` | `bool` | first turn in session |
| `model` | `str` | active model |
| `platform` | `str` | platform (empty string if none) |
| `sender_id` | `str` | user id (empty if none) |
| `**kwargs` | — | `telemetry_schema_version`, more |

**Returns:**

- `{"context": "..."}` → the string is **appended to the user message** before the LLM call
- a plain `str` → same, injected as context
- `None` → no injection (cleanest "nothing to add" signal)

---

## General rules (all hooks)

- Callbacks receive **keyword arguments** — always accept `**kwargs` for forward-compat.
- If a callback **crashes**, it's logged and skipped; the agent continues. A bad plugin
  never breaks the agent.
- Only `pre_llm_call` (context injection) and `pre_tool_call` (block) return values
  matter. All session hooks are **fire-and-forget observers**.
- Observer callbacks get `telemetry_schema_version` automatically; `session_id`,
  `task_id`, `turn_id` are separate correlation fields.

---

## Prefr's own `pre_llm_call` (current)

Pfr's hook returns the injected preference block (already shipped):

```python
def pre_llm_call(user_message: str | None = None, **kwargs):
    if not user_message:
        return None
    result = pipeline.preference_pipeline(ctx=ctx, user_message=user_message, **kwargs)
    return {"context": result} if result else None
```

---

## Minimal Prefr session wrapper (skeleton)

```python
_session_state: dict[str, dict] = {}   # keyed by session_id

def on_session_start(session_id, model, platform, **kwargs):
    _session_state[session_id] = {"model": model, "platform": platform, "turns": 0}

def on_session_end(session_id, completed, interrupted, **kwargs):
    st = _session_state.get(session_id)
    if st:
        st["turns"] += 1
        # flush per-turn state here (or leave it, your call)

def on_session_finalize(session_id, platform, **kwargs):
    if session_id is not None:
        st = _session_state.pop(session_id, None)
        # last-chance flush of outgoing session

def on_session_reset(session_id, platform, **kwargs):
    _session_state.pop(session_id, None)   # fresh bucket for the new key
    _session_state[session_id] = {"platform": platform, "turns": 0}
```

## Reference

- `hermes-agent/website/docs/user-guide/features/hooks.md` — full hook reference
- `agent/turn_finalizer.py:668-684` — `on_session_end` invocation (verbatim kwargs)
- `agent/run_agent.py` — `on_session_start` invocation
- `hermes_cli/plugins.py` — `register_hook` / `invoke_hook` mechanics
