Review the conversation above and maintain the user's preference policy library.

## PURPOSE

Keep the library accurate, durable, and useful for future agent behavior. Be conservative: most reflection passes should make no change.

## PREFERENCE SIGNAL

A preference is a durable way the user wants the agent to behave, decide, or work. It generalizes beyond one task or situation. It may be explicit once or inferred from repeated evidence; capture it only when it would otherwise need repeated explanation.

Do not persist:
- temporary tasks, plans, reminders, current circumstances, or isolated project instructions
- incidental personal facts that belong in semantic memory
- assumptions, one-off behavior, or changes made merely to tidy the library
- implementation, environment, or operational details that are not durable preferences

An explicit long-term statement is evidence once; repeated statements and corrections strengthen it. Cite supporting or contradictory transcript lines as observation ids in `evidence.positive_observations` and `negative_observations`. The engine derives confidence.

## POLICY DECISIONS

Before creating policies, determine the smallest set of independently useful durable preferences supported by the conversation. Keep clauses in one policy when they share a scope and jointly define one operating practice. Split only when each has an independent meaning, trigger, and future applicability. Do not split supporting procedures from the broader preference they implement.

Inspect existing policies with `view` when their contents are needed to assess overlap, contradiction, scope, or consolidation. Before updating, view the policy and confirm the conversation supports a real improvement; topical overlap is not enough.

Create only a genuinely distinct preference not already covered. Merge closely related redundant policies when one policy is materially clearer. Archive policies that are obsolete, superseded, or fully absorbed. To replace an id, create the successor with `replaces`; ids are immutable.

Give policies concise, general, future-proof ids, titles, and bodies. State reusable intent, not transcript details, examples, temporary context, or implementation mechanics. The body limit is a ceiling, not a target.

## ROUTING AND IMPORTANCE

Domains are routing contexts, not loose topic labels. Use only genuinely applicable domains and relationships; never pad. Create a narrowly named domain with `create_domain` only when a distinct, recurring context is absent from the registry and improves future policy selection. Do not create domains for one-off topics, keywords, or a single policy. Use `update_domain` only to improve a description; domain ids are immutable.

Set `priority` by importance, not evidence count: 85–95 core, 70–85 strong, 50–70 situational, 30–50 weak. Do not change priority merely because evidence repeats.

## LOOP

Use operations deliberately, treat returned state as authoritative, and continue only while meaningful work remains. When no justified change remains, `exit`.
