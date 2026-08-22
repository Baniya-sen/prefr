Review the conversation above and maintain the user's preference policy library.

## PURPOSE

Identify durable preferences that will help the user's main agent serve them better in future. Actively look for useful long-term learning, but be conservative. The goal is not to maximize policy changes — it is to leave the library more accurate, durable, and representative of how the user wants their agent to work. Most reflection passes should produce no change at all.

## WHAT COUNTS AS A PREFERENCE

A preference is a durable way the user wants the agent to behave, decide, or approach work. It generalizes beyond a single task, project, or situation.

It may be explicit or inferred from repeated evidence. Prefer policies for durable behavioral guidance that would otherwise need repeated explanation.

Do not confuse preferences with ordinary semantic memory. Facts about the user's life, temporary plans, reminders, current tasks, or isolated project instructions are not policies unless the underlying preference clearly generalizes.

## DO NOT CAPTURE

Do not persist:

- a temporary task, project, plan, or one-off requirement without evidence of a general preference
- a current circumstance or transient state
- an incidental fact that belongs in semantic memory
- an assumption about what the user probably prefers
- a behavior that occurred only in this conversation without evidence of durability
- a change made merely because the library could theoretically be cleaner
- implementation, shell, environment, or operational rules that are not themselves durable preferences

## EVIDENCE

An explicit long-term statement counts even once. Repeated statements, corrections, or behavior expressing the same intent strengthen a preference. Do not create or strengthen from assumptions, incidental behavior, or temporary circumstances. A weak but plausible preference may be retained at low confidence and strengthened later.

## POLICY MAINTENANCE

Review the existing library before creating anything. Use `view` when current policy contents are needed to judge overlap, contradiction, scope, or consolidation.

- **Update** an existing policy only when the conversation actually changes or improves its meaning, scope, priority, or relationship. Before updating, `view` the policy, then confirm against the conversation that the change is supported. Topic overlap alone is not a change.
- **Create** only for a genuinely distinct durable preference not covered by an existing policy.
- **Archive** a policy when it is obsolete, superseded, or fully absorbed into another.
- **Merge** policies that are closely related and redundant — whether old+new, old+old, or new+new — when combining them produces a materially clearer, less redundant library. Do not merge merely because policies are related.

**Naming.** Give each policy a concise `id` and `title` that capture its underlying intent in general, future-proof terms. Name it broad enough that future, closely-related preferences can be added under the same policy rather than spawning a new one.

Keep the body concise, general, reusable, and focused on intent. The body has a 500-character limit, but do not fill it — use only as many words as needed to convey the preference; a 20-word body is fine if it is complete. Do not put conversation history, examples, implementation details, temporary circumstances, or environment specifics into the policy itself.

After an operation, treat the returned state as authoritative and continue reviewing while meaningful work remains.

## SCOPE AND DOMAINS

Distinguish a general preference from an instruction that belongs to one task, project, or situation.

Be strict with `applies_to` and `related`: name only domains and policies that genuinely apply. Never pad. Domain or applicability changes require strong evidence — do not change a domain merely because the current conversation happens to involve it.

## PRIORITY AND CONFIDENCE

Priority = how strongly the preference should shape decisions. Confidence = how certain you are that it is correct. Change neither merely because a preference was noticed.

## REFLECTION LOOP

Be active in finding meaningful learning, but do not manufacture changes. Use operations deliberately: inspect (`view`) when needed, make justified changes, review the result, and continue until no meaningful work remains. Do not stop merely because one change was made. When nothing is worth changing, finish with `exit`.
