# Prefr

**A small preference engine for AI assistants.**

Prefr gives an assistant a persistent understanding of **how you prefer decisions to be made**.

It sits before the main LLM, detects when personal preferences are relevant, selects the applicable policies, and injects them into the model's context.

```text
User
 ↓
Local classifier
 ↓
Deterministic policy engine
 ↓
Relevant preferences
 ↓
Main LLM
```

### Why?

Most AI memory systems remember **what happened**.

Prefr focuses on something different:

> **How do I prefer decisions to be made?**

For example:

* Prefer local/self-hosted software.
* Prefer open source when alternatives are comparable.
* Avoid vendor lock-in.
* Prefer low-maintenance solutions.
* Prefer long-term value over short-term convenience.

### Design

Prefr deliberately keeps runtime behavior simple:

* 🧠 One small local LLM for classification
* ⚙️ Deterministic policy evaluation
* 📄 Human-readable YAML preferences
* 🔒 No runtime vector database or semantic search
* 🔄 Async reflection for learning
* 🧩 Designed to integrate with Hermes

The classifier decides **whether preferences matter**. It does not make the final decision.

The main assistant still does the reasoning.

### Status

**V1 — actively developed**

The V1 architecture and preference model are currently locked.

See [`SPEC.md`](SPEC.md) for the specification and [`ARCHITECTURE.md`](ARCHITECTURE.md) for implementation details.

### License

MIT
