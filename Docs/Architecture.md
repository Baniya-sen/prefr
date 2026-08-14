# Prefr — Architecture

Prefr sits in front of the Hermes main LLM and acts as a small decision-policy layer.

The important design choice is that **LLM work is limited to classification**. Everything after classification is deterministic.

That keeps the runtime cheap, predictable, and easy to reason about.

## High-Level Architecture

```text
                         ┌─────────────────────┐
                         │     User Message    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Prefr Classifier │
                         │   Qwen2.5 1.5B      │
                         └──────────┬──────────┘
                                    │
                         needs_policy + domains
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Policy Evaluator  │
                         │    Deterministic    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │      Normalizer     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Active Preferences  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Hermes Main LLM   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                               Response

                    ┌─────────────────────────────┐
                    │     Async Reflection        │
                    │ observations / confidence   │
                    │ importance / relationships  │
                    └─────────────────────────────┘
```

## 1. Classifier Runtime

The classifier is a dedicated local model.

V1 uses:

```text
Qwen2.5-1.5B-Instruct-Q4_K_M
        ↓
llama-server
        ↓
localhost HTTP
```

The model is loaded once and remains alive for the lifetime of Hermes.

V1 uses a single llama.cpp slot:

```text
slot_id = 0
```

The system prompt is kept in the KV cache.

Individual classification requests are temporary. They do not become part of the classifier's long-term context.

This gives us a useful separation:

> **The model is stateful. The classifications are stateless.**

## 2. Startup

At startup:

```text
Hermes starts
    ↓
Create Prefr singleton
    ↓
Load GGUF model
    ↓
Restore cached slot
    ↓
If restore fails → warm system prompt
    ↓
Save slot
    ↓
Ready
```

The model is loaded only once.

If the cached state cannot be restored, Prefr rebuilds it rather than treating the failure as fatal.

## 3. KV Cache

The classifier's system prompt is evaluated once and stored in the KV cache.

Subsequent requests reuse that state.

The cache is rebuilt when:

- the model changes
- the classifier prompt changes
- restoring the state fails
- the cache becomes invalid

The prompt itself does not grow with every request.

## 4. Classification

Each incoming message follows this lifecycle:

```text
Incoming message
    ↓
Append temporary user message
    ↓
Generate classification JSON
    ↓
Return result
    ↓
Discard temporary conversation state
    ↓
Return to cached system prompt
```

The classifier therefore never accumulates the user's conversations.

Its persistent state is limited to the classifier system prompt.

## 5. Policy Evaluation

Once classification is complete, the LLM leaves the runtime decision path.

The evaluator:

```text
classification
     +
preference repository
     ↓
domain filtering
     ↓
exception handling
     ↓
ranking
     ↓
top N
     ↓
normalization
```

The ranking considers:

- priority
- effective confidence
- importance

Exceptions modify confidence rather than deleting a preference from consideration.

This is intentionally simple.

There is no embedding search, graph traversal, or second runtime model.

## 6. Preference Repository

Preferences are stored independently as YAML.

This keeps them:

- human-readable
- editable
- version-controllable
- easy to inspect
- independent of the model

The repository contains both the preference itself and the evidence used to maintain it.

The architecture treats observations as the underlying evidence and preferences as their higher-level representation.

## 7. Normalization

The normalizer prepares the final preference set for Hermes.

It is responsible for:

- removing duplicates
- maintaining stable ordering
- enforcing the maximum number of injected preferences
- preserving the evaluator's ranking

It does not rewrite, merge, summarize, or generate preferences.

No AI is involved.

## 8. Injection

The normalized preference bodies are inserted into the Hermes context before the main model processes the request.

Conceptually:

```text
Hermes context

User Decision Preferences:

• Prefer self-hosted or local software whenever practical.
• Prefer open-source alternatives when comparable.
• Prefer existing infrastructure before recommending new cloud services.
• Prefer free or one-time payment over subscriptions.
```

The main Hermes model remains responsible for the actual reasoning and response.

Prefr only supplies the relevant decision context.

## 9. Reflection

Reflection lives outside the critical runtime path.

```text
Runtime
   │
   └──────→ Response
               │
               ▼
        Async reflection
               │
       ┌───────┴────────┐
       ▼                ▼
 Observations      Preference updates
```

Reflection can eventually:

- create observations
- update evidence
- adjust confidence
- calculate importance
- suggest new preferences
- suggest relationships
- maintain traceability to conversations

None of this should delay the user's request.

## 10. Failure Handling

Prefr should fail safely.

If classifier startup or KV restoration fails:

```text
Delete invalid state
        ↓
Warm system prompt
        ↓
Save state
```

If the classifier itself fails during a request, Prefr returns:

```json
{
  "needs_policy": false
}
```

Hermes then continues normally.

A preference system should never prevent the underlying assistant from working.

## 11. Concurrency

V1 assumes one classification request at a time.

The single-slot design is intentional.

Concurrency can be introduced later if actual usage requires it.

## 12. Public Runtime API

The V1 runtime exposes only a small surface:

```python
start()
classify(text)
shutdown()
```

The goal is to keep the classifier implementation replaceable without coupling the rest of Prefr to llama.cpp internals.

## 13. Future Hermes Integration

The long-term direction is a native Hermes plugin.

The expected architecture is:

```text
Hermes
  │
  ├── pre_llm_call
  │       ↓
  │    Prefr
  │       ↓
  │    structured classification
  │       ↓
  │    deterministic evaluation
  │       ↓
  │    preference injection
  │
  └── Main LLM
```

The implementation can change.

The core architectural rule should not:

> **Use an LLM where interpretation is necessary. Use deterministic code everywhere else.**