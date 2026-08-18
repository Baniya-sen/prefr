# Hermes Background Review Agent — Exact Prompts (source-verified)

**Source:** `~/.hermes/hermes-agent/agent/background_review.py`
**Extracted:** 2026-08-16, from the live installed Hermes Agent source tree.

This is the *real* "reflector" in Hermes — **not** a separate reflector prompt, but the
**background review agent**: a forked daemon that replays the conversation after each turn and
asks "should any memory / skill be saved or updated?". It runs with a **tool whitelist limited
to `memory` + `skill_manage`**, shares the main model (and the warm prompt cache), and its
writes go straight to the memory and skill stores — the main conversation and prompt cache are
never touched.

This is the exact mechanism prefr Reflection should mirror: a periodic fork that reviews a
session window and derives/updates durable artifacts (policies) via a restricted toolset,
never mutating the live conversation.

There are **three** prompt variants, selected by config:

| variant | when | what it updates |
|---|---|---|
| `_MEMORY_REVIEW_PROMPT` | memory-only review | memory store |
| `_SKILL_REVIEW_PROMPT` | skill-only review | skill library |
| `_COMBINED_REVIEW_PROMPT` | both (default in this deployment) | memory + skills |

---

## 1. `_MEMORY_REVIEW_PROMPT` (verbatim)

```
Review the conversation above and consider saving to memory if appropriate.

Focus on:
1. Has the user revealed things about themselves — their persona, desires,
preferences, or personal details worth remembering?
2. Has the user expressed expectations about how you should behave, their work
style, or ways they want you to operate?

If something stands out, save it using the memory tool.
If nothing is worth saving, just say 'Nothing to save.' and stop.
```

---

## 2. `_SKILL_REVIEW_PROMPT` (verbatim)

```
Review the conversation above and update the skill library. Be
ACTIVE — most sessions produce at least one skill update, even if
small. A pass that does nothing is a missed learning opportunity,
not a neutral outcome.

Target shape of the library: CLASS-LEVEL skills, each with a rich
SKILL.md and a `references/` directory for session-specific detail.
Not a long flat list of narrow one-session-one-skill entries. This
shapes HOW you update, not WHETHER you update.

Signals to look for (any one of these warrants action):
  • User corrected your style, tone, format, legibility, or
    verbosity. Frustration signals like 'stop doing X', 'this is too
    verbose', 'don't format like this', 'why are you explaining',
    'just give me the answer', 'you always do Y and I hate it', or an
    explicit 'remember this' are FIRST-CLASS skill signals, not just
    memory signals. Update the relevant skill(s) to embed the
    preference so the next session starts already knowing.
  • User corrected your workflow, approach, or sequence of steps.
    Encode the correction as a pitfall or explicit step in the skill
    that governs that class of task.
  • Non-trivial technique, fix, workaround, debugging path, or
    tool-usage pattern emerged that a future session would benefit
    from. Capture it.
  • A skill that got loaded or consulted this session turned out
    to be wrong, missing a step, or outdated. Patch it NOW.

Preference order — prefer the earliest action that fits, but do
pick one when a signal above fired:
  1. UPDATE A CURRENTLY-LOADED SKILL. Look back through the
    conversation for skills the user loaded via /skill-name or you
    read via skill_view. If any of them covers the territory of the
    new learning, PATCH that one first. It is the skill that was in
    play, so it's the right one to extend — but only if it is
    curator-managed. Bundled, hub, pinned, and user-owned skills are
    off-limits to you no matter how relevant (see Protected skills
    below); for those, fall through to the next option.
  2. UPDATE AN EXISTING UMBRELLA (via skills_list + skill_view).
    If no loaded skill fits but an existing class-level skill does,
    patch it. Add a subsection, a pitfall, or broaden a trigger.
  3. ADD A SUPPORT FILE under an existing umbrella. Skills can be
    packaged with three kinds of support files — use the right
    directory per kind:
      • `references/<topic>.md` — session-specific detail (error
        transcripts, reproduction recipes, provider quirks) AND
        condensed knowledge banks: quoted research, API docs, external
        authoritative excerpts, or domain notes you found while working
        on the problem. Write it concise and for the value of the task,
        not as a full mirror of upstream docs.
      • `templates/<name>.<ext>` — starter files meant to be
        copied and modified (boilerplate configs, scaffolding, a
        known-good example the agent can `reproduce with modifications`).
      • `scripts/<name>.<ext>` — statically re-runnable actions
        the skill can invoke directly (verification scripts, fixture
        generators, deterministic probes, anything the agent should run
        rather than hand-type each time).
      Add support files via skill_manage action=write_file with
    file_path starting 'references/', 'templates/', or 'scripts/'.
    The umbrella's SKILL.md should gain a one-line pointer to any
    new support file so future agents know it exists.
  4. CREATE A NEW CLASS-LEVEL UMBRELLA SKILL when no existing
    skill covers the class. The name MUST be at the class level.
    The name MUST NOT be a specific PR number, error string, feature
    codename, library-alone name, or 'fix-X / debug-Y / audit-Z-today'
    session artifact. If the proposed name only makes sense for
    today's task, it's wrong — fall back to (1), (2), or (3).

User-preference embedding (important): when the user expressed a
style/format/workflow preference, the update belongs in the
SKILL.md body, not just in memory. Memory captures 'who the user
is and what the current situation and state of your operations
are'; skills capture 'how to do this class of task for this
user'. When they complain about how you handled a task, the
skill that governs that task needs to carry the lesson.

If you notice two existing skills that overlap, note it in your
reply — the background curator handles consolidation at scale.

Protected skills (DO NOT edit these):
  • Bundled skills (shipped with Hermes, e.g. 'hermes-agent').
  • Hub-installed skills (installed via 'hermes skills install').
  • Skills in skills.external_dirs (externally owned).
  • PINNED skills (marked via 'hermes curator pin'). You are an
    autonomous no-user-present actor, so pin blocks your writes too —
    content updates included. Only the user, in a foreground session,
    can change a pinned skill.
  • USER-OWNED skills — anything not curator-managed. A skill the
    user hand-wrote, installed by URL, or asked a foreground agent to
    create is theirs, not yours; your writes to it WILL be refused.
    This includes skills that were loaded or consulted this session:
    being in play does not make one yours to edit. If such a skill is
    wrong or outdated, say so in your reply and recommend
    'hermes curator adopt <name>' — do not try to patch it.
If the only skills that need updating are protected, say
'Nothing to save.' and stop.

Do NOT capture (these become persistent self-imposed constraints
that bite you later when the environment changes):
  • Environment-dependent failures: missing binaries, fresh-install
    errors, post-migration path mismatches, 'command not found',
    unconfigured credentials, uninstalled packages. The user can fix
    these — they are not durable rules.
  • Negative claims about tools or features ('browser tools do not
    work', 'X tool is broken', 'cannot use Y from execute_code'). These
    harden into refusals the agent cites against itself for months
    after the actual problem was fixed.
  • Session-specific transient errors that resolved before the
    conversation ended. If retrying worked, the lesson is the retry
    pattern, not the original failure.
  • One-off task narratives. A user asking 'summarize today's
    market' or 'analyze this PR' is not a class of work that warrants
    a skill.

If a tool failed because of setup state, capture the FIX (install
command, config step, env var to set) under an existing setup or
troubleshooting skill — never 'this tool does not work' as a
standalone constraint.

'Nothing to save.' is a real option but should NOT be the
default. If the session ran smoothly with no corrections and
produced no new technique, just say 'Nothing to save.' and stop.
Otherwise, act.
```

---

## 3. `_COMBINED_REVIEW_PROMPT` (verbatim — the default in this deployment)

```
Review the conversation above and update two things:

**Memory**: who the user is. Did the user reveal persona,
desires, preferences, personal details, or expectations about
how you should behave? Save facts about the user and durable
preferences with the memory tool.

**Skills**: how to do this class of task. Be ACTIVE — most
sessions produce at least one skill update. A pass that does
nothing is a missed learning opportunity, not a neutral outcome.

Target shape of the skill library: CLASS-LEVEL skills with a rich
SKILL.md and a `references/` directory for session-specific detail.
Not a long flat list of narrow one-session-one-skill entries.

Signals that warrant a skill update (any one is enough):
  • User corrected your style, tone, format, legibility,
    verbosity, or approach. Frustration is a FIRST-CLASS skill
    signal, not just a memory signal. 'stop doing X', 'don't format
    like this', 'I hate when you Y' — embed the lesson in the skill
    that governs that task so the next session starts fixed.
  • Non-trivial technique, fix, workaround, or debugging path
    emerged.
  • A skill that was loaded or consulted turned out wrong,
    missing, or outdated — patch it now.

Preference order for skills — pick the earliest that fits:
  1. UPDATE A CURRENTLY-LOADED SKILL. Check what skills were
    loaded via /skill-name or skill_view in the conversation. If one
    of them covers the learning, PATCH it first. It was in play;
    it's the right place — provided it is curator-managed. Protected
    and user-owned skills are off-limits however relevant; fall
    through when one of those is the best fit.
  2. UPDATE AN EXISTING UMBRELLA (skills_list + skill_view to
    find the right one). Patch it.
  3. ADD A SUPPORT FILE under an existing umbrella via
    skill_manage action=write_file. Three kinds:
    `references/<topic>.md` for session-specific detail OR condensed
    knowledge banks (quoted research, API docs excerpts, domain
    notes) written concise and task-focused; `templates/<name>.<ext>`
    for starter files meant to be copied and modified;
    `scripts/<name>.<ext>` for statically re-runnable actions
    (verification, fixture generators, probes). Add a one-line
    pointer in SKILL.md so future agents find them.
  4. CREATE A NEW CLASS-LEVEL UMBRELLA when nothing exists.
    Name at the class level — NOT a PR number, error string,
    codename, library-alone name, or 'fix-X / debug-Y' session
    artifact. If the name only fits today's task, fall back to (1),
    (2), or (3).

User-preference embedding: when the user complains about how
you handled a task, update the skill that governs that task —
memory alone isn't enough. Memory says 'who the user is and
what the current situation and state of your operations are';
skills say 'how to do this class of task for this user'. Both
should carry user-preference lessons when relevant.

If you notice overlapping existing skills, mention it — the
background curator handles consolidation.

Protected skills (DO NOT edit these):
  • Bundled skills (shipped with Hermes, e.g. 'hermes-agent').
  • Hub-installed skills (installed via 'hermes skills install').
  • Skills in skills.external_dirs (externally owned).
  • PINNED skills (marked via 'hermes curator pin'). Pin blocks
    autonomous writes entirely — content updates included — because no
    user is present to consent. Only a foreground session can change one.
  • USER-OWNED skills — anything not curator-managed (hand-written,
    URL-installed, or created by a foreground agent at the user's
    request). Your writes to these WILL be refused, including to skills
    loaded or consulted this session. If one is wrong, say so in your
    reply and recommend 'hermes curator adopt <name>' instead.
If the only skills that need updating are protected, say
'Nothing to save.' and stop.

Do NOT capture as skills (these become persistent self-imposed
constraints that bite you later when the environment changes):
  • Environment-dependent failures: missing binaries, fresh-install
    errors, post-migration path mismatches, 'command not found',
    unconfigured credentials, uninstalled packages. The user can fix
    these — they are not durable rules.
  • Negative claims about tools or features ('browser tools do not
    work', 'X tool is broken', 'cannot use Y from execute_code'). These
    harden into refusals the agent cites against itself for months
    after the actual problem was fixed.
  • Session-specific transient errors that resolved before the
    conversation ended. If retrying worked, the lesson is the retry
    pattern, not the original failure.
  • One-off task narratives. A user asking 'summarize today's
    market' or 'analyze this PR' is not a class of work that warrants
    a skill.

If a tool failed because of setup state, capture the FIX (install
command, config step, env var to set) under an existing setup or
troubleshooting skill — never 'this tool does not work' as a
standalone constraint.

Act on whichever of the two dimensions has real signal. If
genuinely nothing stands out on either, say 'Nothing to save.'
and stop — but don't reach for that conclusion as a default.
```

---

---

## Mechanics — how it actually runs (source-verified)

Answers to the design questions, all traced to `agent/background_review.py`,
`agent/turn_context.py`, `agent/turn_finalizer.py`, `agent/agent_init.py`, and
`tools/skill_manager_tool.py`.

### 1. How does it know which skills the user has, and their content?

It does **not** get a pre-loaded catalog. Three things give it visibility:

- **Toolset** — the fork runs with `review_toolsets = ["skills"]` (+ `"memory"` if enabled).
  The `skills` toolset exposes `skills_list`, `skill_view`, `skill_manage`. The model must
  **actively call** `skills_list` to enumerate, then `skill_view` to read a skill's content.
  Nothing is auto-injected into its context beyond the prompt.
- **Inherited system prompt** — the fork pins the parent's cached system prompt verbatim
  (`review_agent._cached_system_prompt = agent._cached_system_prompt`), so the **skills index**
  (name + 57-char description list) is already in its context from the parent's turn.
- **Replayed conversation history** — the full `messages_snapshot` is passed as
  `conversation_history`, so any skill the session already loaded via `/skill-name` or
  `skill_view` is visible in the transcript (its content is in the tool results).

### 2. Does Hermes provide tool calls to it?

Yes — a **thread-scoped whitelist**. In `_run_review_in_thread`:

```python
review_toolsets = ["skills"]
if review_agent._memory_enabled or review_agent._user_profile_enabled:
    review_toolsets.insert(0, "memory")
review_whitelist = {t["function"]["name"] for t in get_tool_definitions(
    enabled_toolsets=review_toolsets, quiet_mode=True)}
set_thread_tool_whitelist(review_whitelist, deny_msg_fmt="...Only memory/skill tools are allowed.")
```

So the fork gets **only** `skills_list`, `skill_view`, `skill_manage`, and (if memory enabled)
`memory`. Every other tool is denied at runtime. It is also explicitly told in the prompt:
*"You can only call memory and skill management tools. Other tools will be denied at runtime."*

### 3. How many turns does it take / how restricted?

- **Iterations:** the fork is `AIAgent(..., max_iterations=16)` — up to 16 tool-loop iterations
  inside a single review pass.
- **Cadence (when it fires):** turn-based counters, both defaulting to **10**:
  - memory: `agent._memory_nudge_interval = 10` (config `memory.nudge_interval`), counted in
    **user turns** (`_turns_since_memory += 1` per user turn in `turn_context.py`).
  - skills: `agent._skill_nudge_interval = 10` (config `skills.creation_nudge_interval`), counted
    in **tool iterations** of the live turn (`_iters_since_skill` in `turn_finalizer.py`).
- **Timing:** fires **after** the response is delivered (`turn_finalizer.py`:
  `if final_response and not interrupted and (...)`), never competing with the live task.
- **Restrictions:** `skip_memory=True` (no external provider side-effects), `_persist_disabled=True`
  (never writes to the real session DB), `compression_enabled=False` (never compresses the parent),
  `_end_session_on_close=False` (never finalizes the parent session), and a non-interactive
  approval callback that auto-denies any dangerous terminal command.

### 4. Does it do all in one pass?

Yes. It's a **single `run_conversation`** with one `user_message` (the review prompt + tool
restriction) and the replayed history. Inside that one pass it may make up to 16 tool calls
(`skills_list` → `skill_view` → `skill_manage` patch/create). If routed to a *different* aux
model (cache cold), the history is collapsed to a digest (`_digest_history`, tail=24); on the
main model it replays the **full** snapshot (warm cache reads).

### 5. How does it verify it already retrieved a skill before editing it?

Two guards:

- **Read-before-write marks** (`skill_manager_tool.py`): `skill_view` calls
  `mark_background_review_skill_read(path)` when the current origin is `background_review`.
  Write paths (`skill_manage` patch/create/delete) then require the target path to be in the
  read set. Result: the review fork **cannot patch a skill it only inferred from the transcript** —
  it must have actually `skill_view`-ed that file this pass.
- **Prompt-level ordering** — the prompt says "UPDATE A CURRENTLY-LOADED SKILL. Look back through
  the conversation for skills loaded via /skill-name or skill_view", plus `skills_list`/`skill_view`
  to discover existing umbrellas before patching.

### 6. Cooldown and idle time — do they exist?

**No cooldown. No idle-time gate.** Background review is purely **turn-counter based**: fire when
the counter reaches `nudge_interval`, then reset to 0. There is no "wait 2 hours between reviews"
and no "only after 15 min idle."

The `idle_*` / `cooldown` code in `turn_context.py` is a **different subsystem** — opt-in
*idle-triggered context compaction* (`idle_compact_after_seconds`), not the review. Don't confuse
the two.

> **Important for prefr:** Sir's proposed `direct` cadence adds two things Hermes does **not**
> have — **required idle time (15 min)** and **cooldown (2 hours)**. Those are Sir's own
> refinements, not borrowed from Hermes. Hermes' model is simpler: "every N turns, reset the
> counter." If prefr wants idle+cooldown gating, that's new logic the source does not provide a
> template for — it would need to be designed (turn counter AND wall-clock idle AND cooldown),
> which is strictly more complex than what Hermes ships.

---

## What maps to prefr Reflection (the takeaway)

This is the closest thing to what Sir's `direct` mode should be. Key parallels:

| Background review agent | prefr Reflection equivalent |
|---|---|
| fork a daemon thread after the turn, replay the conversation | direct mode fires on a cadence (every 15 turns) over a session window |
| tool whitelist = `memory` + `skill_manage` only | agent gets create/update/merge *functions*, never direct YAML writes |
| "Be ACTIVE — a pass that does nothing is a missed opportunity" | direct mode should default to producing updates, not to skipping |
| preference order: update-loaded → update-umbrella → add-support-file → create-new | Sir's ordering: update existing → merge existing → update umbrella → create new |
| "class-level, not one-session-one-skill" | "don't create a policy for a fact already fetchable by search" (anti-bloat) |
| "Do NOT capture: env-dependent failures, negative tool claims, transient errors, one-off narratives" | the semantic-search gate + "is this durable or transient?" test |
| "Nothing to save." is a real option but not the default | skip is legitimate, but only after the update/merge/create order is checked |
| protected/user-owned skills off-limits to the autonomous actor | policies the user hand-authored are off-limits to autonomous reflection |

The one thing background review does NOT have that Sir's design *does*: an explicit
**semantic-search gate** ("does this already live in short-term memory that's fetchable?").
Hermes just says "save if it stands out" and relies on the model to not bloat. prefr's
explicit "search first, don't create if already fetchable" is a stricter, better version of
that implicit instinct.
