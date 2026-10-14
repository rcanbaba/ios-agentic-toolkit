---
name: feature-inventory
description: Build a complete, independently verified feature inventory of an existing iOS app as the baseline for migrating or rewriting it. Extracts enumerable sources of truth from code (API methods, realtime messages, routes, push types, files), runs parallel area agents, measures their coverage against that baseline, reconciles the parts and has independent agents verify them. Read-only on source; writes only under .migration/. Use when the user wants to migrate, port or rewrite a legacy app, asks "what does this app actually do", or needs a complete feature/flow/identifier list before a large change.
argument-hint: "[source root, e.g. App/ ; optional notes on area split or focus]"
allowed-tools: Read, Glob, Grep, Agent, Bash(git check-ignore *), Bash(python3 *extract_enumerations.py *), Bash(python3 *validate_inventory_part.py *), Bash(python3 *merge_inventory.py *), Bash(python3 *reconcile_inventory.py *), Bash(python3 *apply_verification.py *), Bash(python3 *render_inventory.py *)
---

# Feature Inventory

Produce an inventory of everything the existing app does, precise enough that
a new app can be built from it and checked against it. The inventory is
**as-is**: what the code does today, with evidence. What the new app *should*
do is not decided here (see the `flow-spec` skill).

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Tools live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. Contracts:
`${CLAUDE_PLUGIN_ROOT}/schemas/feature-inventory-part.schema.json` and
`${CLAUDE_PLUGIN_ROOT}/schemas/inventory-verification.schema.json`. A complete
small example is `${CLAUDE_PLUGIN_ROOT}/examples/migrations/pocket-threads/`.

Input: $ARGUMENTS

## Read-only contract

- Source, tests, project files and dependencies are never modified, by you or
  by any agent you spawn. Agents get this rule in their prompt.
- The only writes are under `.migration/` in the current repository, plus a
  line in `.git/info/exclude`.
- Before writing, run `git check-ignore -q .migration/x`; if it is not
  ignored, append `.migration/` to `.git/info/exclude` (local only; never
  edit the project's tracked `.gitignore`).

## Why this shape

A large app (hundreds of files) does not fit one context, and one agent
reading it all produces a plausible but incomplete list. The method here is:
a **deterministic baseline** extracted from code, **parallel authors** whose
output is measured against that baseline, a **reconciliation** step for what
parallel authors cannot see, and **independent verification** by agents that
did not write the parts. In the run this was derived from, coverage was
complete after reconciliation, but independent verification still corrected
most core features. Never skip step 5.

## 1. Baseline: extract enumerations

Survey the project (Glob/Grep, a few targeted reads) to locate the
enumerable sources of truth. Typical ones:

| Source of truth | Where to look | kind |
|---|---|---|
| API client methods, including internal ones and extensions; `exclude` the non-API helpers (generic fetch/download, multipart body builders, cancel-all) | the networking layer | `methods` |
| API path enum; paths with no client method | next to the client | `enum`; `difference` |
| Incoming realtime message types; those parsed but consumed nowhere | socket / realtime layer | `enum`; `unconsumed` |
| Outgoing realtime action types, realtime request payloads | socket / realtime layer | `enum` / `regex` |
| Route enum and its sub-route enums; tab aliases | navigation / router, tab bar | `enum` |
| Push notification types, deeplink actions and keys | push / deeplink handlers | `enum` / `regex` |
| Media/stream SDK wrapper methods and SDK events | the wrapper around the SDK | `methods` / `enum` |
| SDK delegate callbacks implemented, and not implemented | conforming types; the SDK's headers in Pods | `conformance` with `requirements` |
| Engine / encoder configuration types | SDK setup code | `regex` |
| Third-party SDKs | Podfile.lock, the project's Swift packages, vendored frameworks | `dependencies` |
| Notification.Name constants with poster/observer counts | anywhere | `regex` with `counts` |
| UserDefaults keys, feature flags, analytics event types | settings / analytics | `regex` / `enum` |
| Info.plist, entitlements, privacy manifest keys | the app target | `plist` |
| Localization keys | `.strings` / `.xcstrings` | `strings` |

Write `.migration/enumerations.config.json` (format in the docstring of
`extract_enumerations.py`), one `extract` entry per source of truth, with
`field` set to the inventory field it backs (`api_methods`, `ws_incoming`,
`ws_outgoing`, `push_types`, `app_routes`; `null` for informational keys,
which get text coverage instead). Set `call_site_patterns` for the project's
real call forms now (see step 4).
Then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/extract_enumerations.py .migration/enumerations.config.json --out .migration/inventory/enumerations.json
```

Check the counts against the code before continuing: open the API client
and compare the method count with your own quick count; make sure methods
without an access modifier (internal) and methods in extensions are present,
that `excluded` holds only helpers, and that methods whose request is built
over several lines still have a `path`.
Fix the config until nothing is reported as "not found" and the counts are
credible. Everything downstream measures against this file.

## 2. Area agents in parallel

Split the source tree into **at most 8 areas** by directory. Every directory
belongs to exactly one area; shared layers (networking, navigation, push,
utilities) get an area of their own. Record the split in
`.migration/inventory/areas.json` (`{"<area>": {"title": "...", "paths": [...]}}`)
so verification scopes and re-runs can refer to it.

Show the user the baseline counts, the area split and how many agents this
run will start (areas now, then one verifier per flow scope plus a hunter).
**Wait for confirmation before spawning any agent**: the run is the most
expensive in the toolkit, and the user may want to correct the split.

Core/high features need a flow whose every step carries `file:line`
evidence; the validator rejects steps without it or with lines outside the
file.

For each area, spawn one agent (fresh context, parallel) with the prompt in
`${CLAUDE_SKILL_DIR}/area-agent-prompt.md`, placeholders filled. Each agent
writes exactly one file, `.migration/inventory/parts/<area>.json`, and must
run `validate_inventory_part.py` on it until it is valid before reporting.

When an agent reports, run the validator yourself. Invalid parts go back to
the same agent with the validator output; do not fix content yourself (you
have not read that code), only formatting-level issues.

## 3. Merge and measure coverage

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_inventory.py --migration-dir .migration
```

Read `.migration/inventory/coverage.json`, not just the summary line:

- `coverage.<field>.unreferenced`: baseline identifiers no feature claims.
  Some are dead code; most are features that an author described without
  naming the identifier. Step 4 attaches them.
- `unknown_identifiers`: names that are not in the baseline. Authors invented
  or misspelled them; send them back to the author.
- `files.uncovered` / `nonexistent_claimed` / `claimed_by_multiple`
- `dangling_depends_on`: ids that do not exist (parallel authors guess
  cross-area ids). Step 4 maps them.
- `duplicate_ids`, `core_high_without_flow`, `problems` (per-part validator
  errors)
- `text_coverage`: for informational keys (API paths, SDKs, notification
  names, plist keys, unconsumed messages, ...), which names no feature
  mentions. These are leads for features nobody described, not errors.

## 4. Reconcile

Reconciliation attaches unreferenced identifiers to the features whose files
call them. It needs the project's real call forms in
`call_site_patterns` (config): e.g. `\.{name}\(` for API methods,
`\b{type}\.{name}\b`, `navigate\(to:\s*\.{name}\b` and `\(\.{name}\)` for
routes and sub-routes (`{type}` is the declaring enum). Route patterns must be
route-shaped: a bare `.{name}` matches SwiftUI tokens like `.main`, `.center`
or `.cancel`, so the script refuses it. An identifier whose call sites belong
to more than two features is never attached automatically; it is reported as
ambiguous. Reconcile also moves `"path (note)"` source files into
`source_file_notes`.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_inventory.py --migration-dir .migration [--overrides .migration/reconcile.overrides.json]
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_inventory.py --migration-dir .migration
```

Read `.migration/inventory/reconciliation.json`:

- `dead_identifiers`: no call site anywhere. Leave them; they appear in
  the rendered inventory as candidates for not porting.
- `ambiguous`: the call-site file belongs to several features. Read the
  call site and decide which feature owns the call; record the answer as an
  `add` patch in a verification file (step 5) or, if obvious, as an edit to
  the part. Only use `--attach-ambiguous` when you accept over-attribution.
- `unresolved_depends_on`: map them in `reconcile.overrides.json`
  (`"depends_on": {"wrong": "right-id"}`) after checking both features.

Re-run reconcile + merge until `coverage.json` shows no unknown identifiers,
no dangling `depends_on`, no duplicate ids, no uncovered files and only dead
identifiers unreferenced.

## 5. Independent verification

Define verification **scopes by end-to-end flow**, not by area (a flow
crosses areas, and that is where authors disagree). Write
`.migration/verification/scopes.json`:
`{"<scope>": {"features": [ids...], "flow": "one-line description"}}`.
Every core/high feature must be in at least one scope.

Spawn one verifier per scope with `${CLAUDE_SKILL_DIR}/verifier-agent-prompt.md`,
and one extra agent with `${CLAUDE_SKILL_DIR}/missing-feature-hunter-prompt.md`
that sweeps every interaction site, push type, route, flag and realtime
handler for features the inventory does not have. Verifiers must be fresh
agents, never the author of the parts they check. Each writes
`.migration/verification/<scope>.json` and self-checks with
`apply_verification.py --dry-run --scope <scope>` until valid.

Then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/apply_verification.py --migration-dir .migration
```

Read its output and `.migration/verification/applied.json`:

- `skipped` with `replace_no_unique_match`: a replace whose `old` matched no
  item or several. Nothing was changed. Open the feature and the code, then
  write the corrected patch (exact `old`) in `orchestrator.json`.
- `skipped` otherwise: unknown feature ids or existing ids for new features.
- `annotate_unmatched`: a known-issue verdict that matched no unique issue;
  nothing was annotated. Settle it the same way.
- Two verifiers disagreeing on the same feature: decide by reading the code
  directly, record the outcome as a patch of your own in
  `.migration/verification/orchestrator.json`, and apply again.
- Duplicate features found by verifiers: list `["keep-id", "drop-id"]` in
  `reconcile.overrides.json` → `merge_features`, then re-run reconcile. The
  merge keeps every list item, the higher criticality and both summaries, and
  replaces the dropped id in `scopes.json` and flow specs; patches written
  against the dropped id still apply to the kept feature.

Finish with reconcile → merge → render:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/reconcile_inventory.py --migration-dir .migration --overrides .migration/reconcile.overrides.json
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/merge_inventory.py --migration-dir .migration
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/render_inventory.py --migration-dir .migration --title "<App> feature inventory"
```

If a scope's verifier corrected more than about half of its features, that
scope was weakly authored: run a second verifier on it with the corrected
parts before calling it done.

## 6. Report

Show the user, in chat: feature counts by criticality, coverage per baseline
field and for files, dead identifiers, the number of corrections verification
made, remaining open questions, and the path to
`.migration/inventory/INVENTORY.md`. Point out anything you decided by
direct code read.

End with: "No source files were modified. Next: `/flow-spec` for the
critical flows."

## Rules for every agent you spawn

Include these verbatim in the prompts (the templates already do):

- Read-only on the repository; write only the one file you are assigned.
- Identifiers are exact names from `enumerations.json`, one per list item.
  Never `"a, b"`, never a guessed name, never a prose description in an
  identifier field.
- Describe current behavior only. Target behavior, opinions and "should" go
  to `open_questions` (authors) or are left out (verifiers).
- Every claim a verifier makes carries `path/File.swift:line` evidence, and
  so does every step of a core/high flow.
- `source_files` are bare paths; remarks go to `source_file_notes`.
- Guesses are not facts: put them in `open_questions`.
