# Flow-spec agent prompt template

Used by the `flow-spec` skill, step 2. One fresh agent per flow, in parallel.
Fill every `{{...}}` placeholder.

---

You are specifying one end-to-end flow of an existing iOS app as a state
machine, precisely enough that a new app can be implemented from it and
tested for parity. Describe **current behavior as the code implements it**.

Flow: `{{FLOW_ID}}` — {{TITLE}}
Related inventory features: {{RELATED_FEATURES}}
Source root: `{{SOURCE_ROOT}}`
Inventory: `{{MIGRATION_DIR}}/inventory/inventory.json` (read your related features by id; they list the screens, files and identifiers to start from)
Contract: `{{PLUGIN_ROOT}}/schemas/flow-spec.schema.json`
Output files (the only files you may write):
`{{MIGRATION_DIR}}/flow-specs/{{FLOW_ID}}.json` and the rendered `{{FLOW_ID}}.md`

## Rules

1. Read-only on the repository.
2. Start from the related features' `source_files` and follow the flow in
   code from every entry point to every exit, including cleanup.
3. States are what the app is in (snake_case ids; the first state is the
   initial one). For each: actor, what the user sees, which resources are
   held (media channel and role, realtime subscriptions, timers, capture).
   If the flow has several entry points (a push, a deeplink, a screen), list
   their states in `entry_states`; every state must be reachable from one.
   If this flow is a variant of another spec, set `base_flow` and specify
   only what differs; say what is out of scope in `scope_notes`.
4. Events are what moves the machine: user actions, API responses, realtime
   messages, SDK callbacks, system events, timers, with the exact identifier.
5. Every transition has ordered `actions` using exact identifiers
   (`api:<method>`, `ws_out:<action>`, `sdk:<call>`, `ui:<...>`,
   `analytics:<...>`, `timer:<...>`) and `path/File.swift:line` evidence.
   The validator checks that every evidence file exists and the lines are
   inside it; read the line before you cite it. Use `"*"` as `from` for
   transitions that apply in any state.
6. Completeness: every `api_methods`, `ws_incoming` and `ws_outgoing`
   identifier of the related features must appear in the spec (event
   identifier or action) or be listed in `excluded_identifiers` with an
   honest reason. Do not exclude something because it was hard to place.
7. `interruptions` (ids `INT-n`): at least background/foreground, network
   loss, realtime reconnect, app kill and relaunch, another flow starting
   (a call, another session), token or session expiry, permission revoked.
   Record the current behavior with evidence, even when it is "nothing
   happens".
8. `failure_handling` (ids `FH-n`): every API or realtime failure the flow
   can hit, with the current behavior and evidence.
9. `invariants` (ids `INV-n`): properties that must always hold (resource
   cleanup on every exit path, ordering, single-session rules), with evidence
   where the code enforces them.
10. `as_is_bugs`: observed defects with evidence and impact. Observations,
    not fixes.
11. `open_decisions` (ids `OD-n`): every place where the target behavior
    must be decided by a person. Give current behavior and options. **Never
    decide them yourself** and never put target behavior anywhere else.
    Leave `decision` and `decided_on` null. "Same as the old app" is not a
   decision you can make either.
12. `acceptance_tests` (ids `AT-n`): given/when/then with `covers` listing
    `happy_path`, `INV-n`, `INT-n`, `FH-n`, or `behavior` for a plain
    behavior test. Every invariant, interruption and failure item must be
    covered, and at least one test covers the happy path.
13. Never edit the `.md`: it is generated from the JSON. Validate and render
    until valid:
    `python3 {{PLUGIN_ROOT}}/scripts/validate_flow_spec.py {{MIGRATION_DIR}}/flow-specs/{{FLOW_ID}}.json --migration-dir {{MIGRATION_DIR}}`
    `python3 {{PLUGIN_ROOT}}/scripts/render_flow_spec.py {{MIGRATION_DIR}}/flow-specs/{{FLOW_ID}}.json`

## Report back

Reply with: counts (states, events, transitions, invariants, interruptions,
failures, bugs, open decisions, tests), the identifiers you excluded and why,
the open decisions as one line each, and anything you could not determine
from code. Do not paste the JSON.
