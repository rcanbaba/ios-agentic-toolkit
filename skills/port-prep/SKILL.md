---
name: port-prep
description: Prepare the port of a legacy iOS app's core layer into a new app after feature-inventory and flow-spec. Computes the core layer's type-dependency closure, finds coordinators and domain models tangled into UI files, finds extensions in screen files that change how core types decode or encode, and starts a porting ledger for shims and gaps. Read-only on the legacy app; writes only under .migration/port/. Use when the user is about to start porting or asks what must move first.
argument-hint: "[core layer paths, e.g. App/Networking App/Realtime App/Models]"
allowed-tools: Read, Glob, Grep
---

# Port Preparation

The inventory and flow specs say **what** the app does. Before the first
feature is ported, find out what the core layer (networking, realtime,
models, managers) **needs** in order to move, and what UI code it is
secretly tangled with. In the run this was derived from, extensions in screen
files changed how core models decoded; a port without them compiles and
decodes differently, with no error.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).

Input: $ARGUMENTS

## Prerequisites and contract

- `.migration/inventory/inventory.json`, the flow specs and `AUDIT.md` exist
  (feature-inventory and flow-spec skills). If the audit has open
  `data-loss` or `wrong` findings, say so and stop.
- Read-only on the legacy app. Writes only under `.migration/port/`.
- Nothing is ported here. This skill ends with a plan and a ledger.

## 1. Core layer boundary → human confirms

Propose the core layer: the directories and types that have no UI
(networking, realtime, persistence, models, managers, SDK wrappers). List
them with file counts. **Wait for the user to confirm or edit the
boundary.**

## 2. Type-dependency closure

Starting from the core types, follow every type they reference (properties,
parameters, return types, generic arguments, conformances, extensions) until
no new type appears. For each type in the closure record where it is
declared. Write `.migration/port/core-closure.md`:

| Type | Declared in | Pulled in by | In a UI file? |
|---|---|---|---|

Every type declared in a UI file (a view, view controller or screen folder)
is a tangle: it must move into the core or be replaced before the core can
compile on its own.

## 3. Untangle

- **Coordinators**: types that both navigate and hold domain logic or state
  (they call the API client, own realtime subscriptions, cache data). Split
  them into a UI coordinator and a domain service; list the split.
- **Domain models in UI files**: models, enums and DTOs declared inside
  screen files. List each with its target location in the core.
- **Decoding and encoding changes**: search outside the core for anything that
  changes how a core type is decoded or encoded:
  `extension <CoreType>: Decodable`, `init(from decoder:)`, `encode(to:)`,
  `CodingKeys`, custom `JSONDecoder` strategies, `@propertyWrapper` used in
  models. Each one must move with the type, or the new app decodes the same
  JSON differently.

Write the results to `.migration/port/untangle.md`, each item with
`path/File.swift:line` evidence.

## 4. Porting ledger

Start `.migration/port/LEDGER.md`. It lives for the whole port: every
temporary shim, adapter, stub and known gap is recorded when it is created
and closed when it is removed.

| # | Item | Kind | Legacy location | New location | Why | Remove when | Status |
|---|---|---|---|---|---|---|---|

Kind is `shim`, `adapter`, `stub`, `gap` (behavior not yet ported) or
`moved` (a type that changed place in step 3). Seed it with the items from
steps 2 and 3.

## 5. Report

In chat: the confirmed core boundary, closure size, the tangles by kind
(coordinators, models in UI files, decoding changes), the ledger's first
items, and the paths. End with: "No source files were modified."
