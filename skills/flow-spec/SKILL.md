---
name: flow-spec
description: Write validated, as-is state-machine specifications for the critical end-to-end flows of an existing iOS app, from a feature inventory produced by the feature-inventory skill, then collect the open product decisions, group them into cross-cutting rules and record the decisions. Read-only on source; writes only under .migration/flow-specs/ and the decision logs. Use after feature-inventory, when the user asks for flow specs, state machines, acceptance tests or the decisions needed before porting a legacy app.
argument-hint: "[flow ids, or 'critical' to derive the list from the inventory]"
allowed-tools: Read, Glob, Grep, Agent, Bash(python3 *validate_flow_spec.py *), Bash(python3 *render_flow_spec.py *)
---

# Flow Spec

Turn the critical flows of the existing app into state machines with
evidence, invariants, interruption and failure behavior, as-is bugs,
acceptance tests and open decisions. A flow spec is what the new app is
built and tested against.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Contract: `${CLAUDE_PLUGIN_ROOT}/schemas/flow-spec.schema.json`. Example:
`${CLAUDE_PLUGIN_ROOT}/examples/migrations/pocket-threads/migration/flow-specs/`.

Input: $ARGUMENTS

## Prerequisites and contract

- `.migration/inventory/inventory.json` exists and its `coverage.json` is
  clean (feature-inventory skill, steps 1–5). If not, stop and say so.
- Read-only on source. Writes only under `.migration/flow-specs/`,
  `.migration/PENDING_DECISIONS.md` and `.migration/DECISIONS.md`.
- Specs describe **current behavior**. Agents never decide target behavior;
  every "should" becomes an `open_decisions` entry.

## 1. Choose the flows → human confirms

From the inventory: every `core` feature, grouped with the features it
`depends_on` and the features that depend on it, forms a candidate flow.
Merge candidates that share a session (the same screen or the same live
resource). Typical result: 5–10 flows such as "start and end a session",
"join as a participant", "1:1 call", "purchase and unlock".

Propose the list with, per flow: id, title, related feature ids, and why it
is critical. **Wait for the user to confirm or edit the list.**

## 2. One agent per flow

Spawn one fresh agent per flow (parallel) with
`${CLAUDE_SKILL_DIR}/flow-spec-agent-prompt.md`, placeholders filled. Each
writes `.migration/flow-specs/<flow_id>.json`, validates it with
`validate_flow_spec.py`, renders `<flow_id>.md` with `render_flow_spec.py`,
and reports back.

Run the validator yourself on every spec. The validator enforces: state and
event references, `file:line` evidence on transitions, interruptions,
failures and bugs, reachability of every state, identifier completeness
against the related features (or an explicit exclusion with a reason), and
acceptance-test coverage of the happy path, every invariant, interruption
and failure item. Invalid specs go back to their agent with the output.

Then read each rendered `.md` and check what a validator cannot:
- exclusions are honest (an identifier that *is* part of the flow must not
  be excluded for convenience)
- interruptions cover at least: background/foreground, network loss and
  reconnect, app kill, another flow starting, token/session expiry,
  permission revoked
- `open_decisions` contain the "should"s; the spec body contains none
- `as_is_bugs` are observations with evidence, not opinions

Where two specs describe the same shared behavior differently (a shared
teardown, a shared reconnect handler), decide by reading the code and send
the correction to the agent whose spec is wrong.

## 3. Collect decisions → human decides

Gather every `open_decisions` entry across specs into
`.migration/PENDING_DECISIONS.md` in three groups:

- **A. Cross-cutting rules**: questions that recur across flows (exit
  cleanup on every exit path, resync after interruption, keeping realtime
  connections alive in background, concurrent sessions, token renewal,
  idempotency of paid or irreversible actions, user feedback on silent
  failures, ...). Each rule gets an id (`A1`, `A2`, ...), the flows it
  applies to and a recommendation. Decide each **once**.
- **B. Default rule**: "replicate current behavior unless a decision says
  otherwise". State it explicitly so undecided questions have an answer.
- **C. Flow-specific questions**: everything else, listed per flow, to be
  decided when that flow is ported.

Present A and B to the user and **wait for their decisions**. They may also
decide items from C now.

## 4. Record and write back

1. Append each decision to `.migration/DECISIONS.md` as a table row:
   date, topic, decision. This log is the source of truth.
2. Write decisions back into the specs: `cross_cutting_decisions` (id, rule,
   decision) in every spec the rule applies to; `open_decisions[].decision`
   and `decided_on` for decided questions; for deferred ones, `decision:
   "defer to porting; default rule: replicate current behavior"`.
3. Re-validate with `--require-decisions` and re-render:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_flow_spec.py .migration/flow-specs/*.json --migration-dir .migration --require-decisions
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_flow_spec.py .migration/flow-specs/*.json
```

## 5. Report

In chat: the flows, per flow the counts (states, events, transitions,
tests, as-is bugs), the cross-cutting rules and their decisions, how many
questions were deferred, and the paths. End with: "No source files were
modified."

## What a later porting step consumes

Per flow: the state machine and acceptance tests (parity checks), the
invariants (review checklist), `cross_cutting_decisions` and decided
`open_decisions` (target behavior), `as_is_bugs` (do not replicate), and
the related features' identifier lists from the inventory (what to wire).
