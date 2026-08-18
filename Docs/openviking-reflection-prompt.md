# OpenViking Reflection (memory extraction) — Exact Prompts & Operation Modes

**Source:** `~/.hermes/hermes-agent/plugins/memory/openviking/` + the installed OpenViking
server package at `~/openviking/lib/python3.12/site-packages/openviking/session/memory/`
**Extracted:** 2026-08-16.

OpenViking is Hermes' external memory provider in this deployment. Its **reflection** is the
`ExtractLoop` — a single ReAct LLM call that reads the current memory state, then outputs
structured write/edit/delete operations. This is the "skip / merge / add" mechanism Sir is
referring to. The agent does NOT write YAML directly — it emits typed operations against a
schema, and `memory_updater.py` applies them.

---

## 1. The reflection orchestrator (`extract_loop.py`)

Docstring (verbatim):

> Simplified ReAct orchestrator for memory updates — single LLM call with tool use.
>
> 0. Pre-fetch: System performs ls + read .overview.md + search (via strategy)
> 1. LLM call with tools: Model decides to either use tools OR output final operations
> 3. If operations output: Return and finish

Only `read` and `search` tools are exposed. There is NO write tool — the model outputs
operations, the engine applies them. That's the "not direct YAML creation but a function
that helps create" pattern, exactly as Sir wants for prefr.

---

## 2. The extraction agent prompt (verbatim — `session_extract_context_provider.py` `instruction()`)

```
You are a memory extraction agent. Your task is to analyze conversations and update memories.

## Workflow
1. Analyze the conversation and pre-fetched context
2. If you need more information, use the available tools (read/search)
3. When you have enough information, output ONLY a JSON object (no extra text before or after)

## Critical
- ONLY read and search tools are available - DO NOT use write tool
- Before editing ANY existing memory file, you MUST first read its complete content
- ONLY read URIs that are explicitly listed in ls/search tool results, returned by previous tool calls

## Target Output Language
All memory content MUST be written in {output_language}.

## URI Handling
The system automatically generates URIs based on memory_type and fields. Just provide correct memory_type and fields.

## Self and Peer Memory
When a memory item describes the current user, omit peer_id.
When a memory item describes a peer, set peer_id to one of the peer_id values allowed by the output schema. Do not invent peer_id values.
For events with ranges, the system derives self/peer targets from the message range.
Message role is authoritative: user-role content is the source for profile/preferences/entities/events, and assistant-role content is the source for cases/patterns/tools/skills. Do not infer ownership from neighboring messages.
```

The system prompt is assembled (in `extract_loop.py`) as:

```
{instruction()}

## Page ID Rules
- Every memory item you create or edit MUST include "page_id".
- For existing items, use the page_id shown in read/search results.
- For new items, assign a unique page_id >= 100.
- When editing an existing item, reuse its existing page_id.

## Link Rules                      (only when link_enabled)
- Link fields `f` and `t` must reference these page_id values.
- Only create links when the relationship is meaningful and clear from the conversation. Do NOT force links between unrelated items.

## Read Format Rules
- The read tool accepts `uri`, optional `offset` (0-indexed), and optional `limit`.
- Read content is returned in Claude Code format: each visible line is prefixed with `line_number<TAB>`.
- When you copy text from read results into SEARCH/REPLACE operations, copy the exact text after the line-number prefix. Never include the line-number prefix itself in `search` or `replace`.

## Output Format
The final output of the model must strictly follow the JSON Schema format shown below:
```json
{schema_str}
```
```

The user message (verbatim, `_build_conversation_message`):

```
## Conversation History
**Session Time:** {time_display} ({day_of_week})
Relative times (e.g., 'last week', 'next month') are based on Session Time, not today.

{conversation}

After exploring, analyze the conversation and output ALL memory write/edit/delete operations in a single response. Do not output operations one at a time - gather all changes first, then return them together.
```

---

## 3. The operation modes (the "skip / merge / add" semantics)

### Per-memory-type operation mode (`MemoryTypeSchema.operation_mode`)

| mode | meaning |
|---|---|
| `upsert` (default) | create if absent, merge/patch if present |
| `add_only` | never edit or delete existing (e.g. `trajectories`) |
| `update_only` | never create new |

### Per-field merge operation (`merge_op`, from `merge_op/base.py` + `factory.py`)

| merge op | meaning |
|---|---|
| `patch` | SEARCH/REPLACE block within a field (line-number aware) |
| `replace` | full replacement, no SEARCH/REPLACE |
| `sum` | additive accumulation (counts, lists) |
| `immutable` | field cannot be changed once set |
| `link_merge` | merge + dedup the `links` field (backlinks, keep original created_at) |

### The operations container (`StructuredMemoryOperations`, `dataclass.py`)

The model's final output is a flat structure with these fields:

- per-memory-type fields (e.g. `preferences`, `entities`, `events`, …) — each a list of
  items to upsert (create-or-merge)
- `delete_uris: List[str]` — explicit deletion
- `links` (optional) — relationship edges
- `is_empty()` → True when no writes, edits, or deletes → **this is the "skip" decision**:
  "no memory operations" is a valid, legitimate output.

Crucially, the model is told (in the user message) to output **ALL operations in a single
response** — the "skip" case is simply an empty operations object, not a separate verb.

---

## 4. What maps to prefr Reflection (the takeaway)

| OpenViking reflection | prefr Reflection equivalent |
|---|---|
| read-only tools (read/search), no write tool | agent gets create/update/merge *functions*, not direct YAML writes |
| model outputs typed operations, engine applies them | `memory_updater`-style applier for policies |
| `upsert` = create-or-merge by default | "update existing → merge → create new" ordering is explicit policy, but the *default* OpenViking leans on is upsert |
| `operation_mode` gates whether a type can be created vs edited | per-domain create/edit permission in prefr |
| `merge_op` per field (patch vs replace vs sum) | how a policy body merges when a new preference overlaps an existing one |
| `is_empty()` = skip | the "don't create a policy" decision (Sir's semantic-search gate) |
| single response, all ops at once | direct mode emits one batch of decisions, not N round-trips |

The key insight Sir already intuited and the source confirms: **OpenViking's reflection does
not do "skip vs merge vs add" as three separate verbs.** It does "produce operations or
produce nothing." Skip = empty. Merge = upsert with a `patch`/`sum`/`link_merge` strategy.
Add = upsert with no existing target. The three-way *decision* is Sir's own refinement —
and it's a good one, because prefr policies are small and few enough that an explicit
ordered decision (update → merge → create) gives tighter control than OpenViking's
"upsert everything" default.
