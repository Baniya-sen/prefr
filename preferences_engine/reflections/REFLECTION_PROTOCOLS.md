# PREFr Reflection Output Protocol

The Reflection agent communicates with the policy engine using one JSON object per turn.

Return **only valid JSON**.
Do not return Markdown, code fences, explanations, comments, or additional text.

## Operation Format

Every response has this structure:

{
  "method": "<operation>",
  "request": [...]
}

Supported operations:

- `view` — inspect existing policies.
- `update` — modify existing policies.
- `archive` — retire existing policies.
- `create` — create new policies.
- `exit` — finish the reflection process.

The `request` value is always a list. Multiple policies may be handled in one operation.

---

## VIEW

Use `view` when the current contents of one or more policies are needed.

Each request requires only `id`.

Example:

{
  "method": "view",
  "request": [
    {"id": "local_first"},
    {"id": "low_cost"}
  ]
}

The policy engine returns the requested policies. The returned state is authoritative and will be available in the next Reflection turn.

---

## UPDATE

Use `update` to modify one or more existing policies.

Each request requires `id` and at least one field to change.

All other policy fields are optional. Fields that are not provided remain unchanged.

Supported mutable fields:

- `id`
- `title`
- `body`
- `priority`
- `applies_to`
- `primary_domain`
- `exceptions`
- `related`
- `evidence`

Example:

{
  "method": "update",
  "request": [
    {
      "id": "local_first",
      "priority": 90,
      "applies_to": [
        "software",
        "infrastructure"
      ]
    }
  ]
}

An existing policy ID may be changed when there is a justified reason to improve its identity. IDs must remain globally unique.

Do not provide fields that do not need to change.

---

## CREATE

Use `create` to create one or more genuinely distinct durable policies.

A create request should provide the policy information that Reflection is responsible for determining:

- `id`
- `title`
- `body`
- `priority`
- `applies_to`

Optional fields:

- `primary_domain`
- `exceptions`
- `related`
- `evidence`

Example:

{
  "method": "create",
  "request": [
    {
      "id": "ask_before_git_push",
      "title": "Ask before pushing",
      "body": "Ask the user for confirmation before pushing changes to a remote repository.",
      "priority": 90,
      "applies_to": ["git"],
      "primary_domain": "git",
      "exceptions": [],
      "related": [],
      "evidence": {
        "positive_observations": ["session_123:17"],
        "negative_observations": []
      }
    }
  ]
}

Evidence observations identify conversation evidence. Do not calculate confidence or evidence counts yourself. The policy engine derives those values.

System-owned metadata such as confidence, evidence counts, timestamps, and creation source is handled by the policy engine.

---

## ARCHIVE

Use `archive` to retire one or more existing policies.

Each request requires only `id`.

Example:

{
  "method": "archive",
  "request": [
    {"id": "obsolete_preference"}
  ]
}

Do not resend the policy contents.

---

## EXIT

Use `exit` when no further meaningful policy work remains.

`request` must be an empty list.

Example:

{
  "method": "exit",
  "request": []
}

---

## General Rules

- Return exactly one JSON object per turn.
- `request` must always be a JSON array.
- Multiple requests may be included in one operation.
- Use only operation names defined above.
- Use only fields defined above.
- Do not invent policy fields.
- Use policy IDs exactly when referring to existing policies.
- Domain values must come from the domains supplied by the system.
- When uncertain about an existing policy's current state, use `view` rather than guessing.
