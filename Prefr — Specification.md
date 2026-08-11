# Prefr — Specification

**V1 — Locked**

Prefr is a preference and decision-policy layer for Hermes.

Its job is simple: understand when a user's long-term preferences matter, select the relevant ones, and make them available to Hermes before the main model answers.

Prefr does **not** make the final decision. It does not replace Hermes, and it does not try to become another agent.

The runtime is deliberately small and predictable:

- One local classifier LLM
- Deterministic policy evaluation
- YAML-based preferences
- No runtime semantic search
- No runtime learning
- Asynchronous reflection for learning and maintenance

> **Runtime is dumb. Reflection is smart.**

## 1. Runtime Flow

```text
User message
    ↓
Classifier
    ↓
Policy evaluator
    ↓
Normalizer
    ↓
Active preferences
    ↓
Hermes main LLM
    ↓
Response
    ↓
Async reflection
```

The classifier only answers whether preferences are relevant and, if so, which domains and interaction mode apply.

The actual preference selection is deterministic.

## 2. Classifier

The V1 classifier is a local **Qwen2.5-1.5B-Instruct-Q4_K_M** model running through `llama-server`.

Its only job is classification.

It must not:

- reason about the final answer
- select individual preferences
- rewrite preferences
- learn from the conversation

Example:

```json
{
  "needs_policy": true,
  "domains": ["software", "infrastructure"],
  "interaction_mode": "recommend"
}
```

When preferences would not materially improve the response:

```json
{
  "needs_policy": false
}
```

The classifier defaults to `needs_policy=false`.

Supported interaction modes:

```text
recommend
compare
decide
plan
learn
troubleshoot
review
automate
brainstorm
other
```

## 3. Preferences

Each preference is stored as its own YAML file.

Example:

```yaml
id: local_first

body: >
  Prefer self-hosted or local software whenever practical.
  Recommend SaaS only when the benefits clearly outweigh the cost.

priority: 90
confidence: 0.94
importance: 73

applies_to:
  - software
  - infrastructure

exceptions:
  - company

related:
  - low_cost
  - open_source

evidence:
  positive: 18
  negative: 2
  representative_observations:
    - obs_183
    - obs_241
  summary: >
    User repeatedly preferred local solutions over SaaS.

created_by: manual
created_at: 2026-08-04
updated_at: 2026-08-04
last_reviewed: 2026-08-04
```

Preference IDs are stable `snake_case` identifiers.

Once created, an ID does not change.

### Core fields

| Field | Purpose |
|---|---|
| `id` | Stable unique identifier |
| `body` | Preference text injected into Hermes |
| `priority` | Relative importance |
| `confidence` | Confidence that the preference reflects the user |
| `importance` | Long-term centrality of the preference |
| `applies_to` | Domains where it is relevant |
| `exceptions` | Preferences that reduce its confidence |
| `related` | Related preferences |
| `evidence` | Supporting observations and history |

## 4. Exceptions

Exceptions do not cancel preferences.

They **dampen their confidence**.

For example:

```yaml
id: local_first
exceptions:
  - company
```

If the user asks about a personal project, `local_first` may retain its full confidence.

If the request concerns a company project and `company` also applies, the confidence of `local_first` is reduced.

V1 uses a configurable dampening factor with a default of `0.4`.

This keeps the original preference in the ranking while allowing context to reduce its influence.

## 5. Policy Evaluation

The evaluator is deterministic.

Given the same classifier output and the same preference repository, it produces the same result.

The process is:

1. Exit if `needs_policy=false`.
2. Filter preferences by domain.
3. Apply exception dampening.
4. Rank using priority, effective confidence, and importance.
5. Keep the top applicable preferences.
6. Normalize the result.
7. Inject the selected preference bodies into Hermes.

There is deliberately no semantic search, embeddings, runtime graph traversal, or runtime LLM involved.

## 6. Observations

Observations are the evidence behind preferences.

A preference is a summary of what the system has learned; observations are the underlying source of truth.

Example:

```yaml
id: obs_183

conversation: conv_183

recommendation:
  PostgreSQL Docker

user_choice:
  PostgreSQL Docker

observation:
  User preferred local deployment.

strength: 0.82

timestamp:
```

In V1, observations are manually recorded.

The reflection system will eventually generate and maintain them automatically.

## 7. Reflection

Reflection runs asynchronously and never blocks the runtime path.

Its responsibilities include:

- extracting observations
- updating positive and negative evidence
- updating confidence
- computing importance
- suggesting preference changes
- suggesting relationships
- suggesting new preferences
- retaining references to the source conversation

The runtime should remain predictable even as the system becomes better at learning.

## 8. Boundaries

Prefr and OpenViking have different jobs.

**OpenViking remembers facts.**

**Prefr remembers how the user prefers decisions to be made.**

Prefr is therefore not intended to become another general-purpose memory system.

## 9. V1 Scope

### Included

- Local classifier
- YAML preference repository
- Deterministic policy evaluator
- Preference injection into Hermes
- Manual preference creation

### Deferred

- Automated reflection
- Automated observation generation
- Native Hermes plugin integration
- Advanced importance/confidence algorithms
- Rich preference relationships
- Cross-domain inheritance

### Explicitly out of V1

- Vector databases
- Semantic retrieval
- Neo4j or graph databases
- Runtime graph traversal
- Runtime policy learning
- Runtime summarization
- Conditions/rule language
- Separate dual-purpose runtime/body fields

These are deliberate constraints, not missing features.

## 10. V2 Direction

Once V1 is validated, Prefr can move into a native Hermes integration.

The intended direction is to use Hermes' structured LLM interface and `pre_llm_call` hook rather than maintaining a separate classifier server.

The architectural principle remains the same:

> **Classify first. Evaluate deterministically. Let the main model reason.**