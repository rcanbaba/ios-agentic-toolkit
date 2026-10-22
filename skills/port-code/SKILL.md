---
name: port-code
description: Port a legacy iOS app's code and assets into a new app, verbatim, driven by build errors. Copies the agreed scope, then loops build → resolve missing symbols and assets from the legacy app → build until green, removing temporary shims as their originals arrive and recording everything in the porting ledger. Runs after port-prep; writes only in the new app. Use when the user starts or continues moving features, screens or the core layer from an old app into a new one.
argument-hint: "<what to port: core | a feature list | the rest> [legacy root] [new app root]"
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(python3 *port_missing_symbols.py *), Bash(python3 *port_assets.py *), Bash(python3 *parity_check.py *), Bash(xcodebuild *), Bash(xcrun simctl *), Bash(cp *), Bash(mkdir *), Bash(git status*), Bash(git diff*)
---

# Port Code

Move legacy code into the new app **unchanged first**, and let the compiler
say what is missing. Behavior is preserved by copying, not by rewriting from
memory; the view layer is rebuilt afterwards with the `ui-port` skill. In the
run this was derived from, about 300 screen files, their dependencies and
their assets reached a green build this way in a handful of rounds, and the
features worked on the first simulator run.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Scripts: `${CLAUDE_PLUGIN_ROOT}/scripts/port_missing_symbols.py` and
`port_assets.py`.

Input: $ARGUMENTS

## Prerequisites and contract

- `.migration/port/` from the `port-prep` skill: the core closure, the
  untangle list and `LEDGER.md`. Decisions in `.migration/DECISIONS.md` are
  the only allowed behavior changes; everything else is replicated.
- The new app builds before you start. Find its build command in its
  CLAUDE.md or README (project generation step, workspace, scheme,
  destination). Use exactly that command; never add a custom
  `-derivedDataPath` (it duplicates gigabytes of build products per run).
- Read-only on the legacy app. Writes only in the new app and in
  `.migration/port/`.
- Nothing is committed. Commit only when the user asks.

## 1. Scope and placement → human confirms

Propose, with file counts:
- **What moves now**: the core layer, a set of features, or "everything
  that is left". Port in large, feature-complete slices; a feature copied
  without its view models or helpers just moves the errors around.
- **What is excluded on purpose** (a feature deferred to the end, a legacy
  design layer that the new design system replaces, a third-party SDK the
  new app drops). Each exclusion becomes a ledger row of kind `gap` with the
  decision that justifies it.
- **The path map**: legacy prefix → new location, written to
  `.migration/port/path-map.json`, for example
  `[["Scenes/Features/", "Features/"], ["Common/", "UI/Common/"]]`.
- **Where legacy assets go**: one catalog folder (for example
  `Assets.xcassets/Legacy`), removed once the UI is rebuilt.

**Wait for the user to confirm.** Then copy the confirmed slice verbatim with
`cp`, preserving the folder structure under the mapped destination. Copy the
decoding/encoding extensions listed in `untangle.md` together with their
types.

## 2. Build loop

Repeat until the build is green or a round makes no progress:

1. Regenerate the project if it is generated (XcodeGen, Tuist) so new files
   are part of the target, then build with the project's command and keep
   only the error lines:
   `... build 2>&1 | grep -E "error:" | sort -u > .migration/port/build-errors.txt`
2. Plan, read, then apply:
   ```sh
   python3 scripts/port_missing_symbols.py --legacy <legacy> --target <new app src> \
       --errors .migration/port/build-errors.txt --path-map .migration/port/path-map.json \
       --exclude "<excluded globs>" [--apply]
   python3 scripts/port_assets.py --legacy-catalog <legacy>/Assets.xcassets [...] \
       --target-src <new app src> --into <catalog folder> \
       --errors .migration/port/build-errors.txt --scan [--apply]
   ```
   Run each without `--apply` first and read the plan: a planned file from
   an excluded area means the exclusion leaks (something in scope depends on
   it). Decide with the user before copying it.
3. Handle what the scripts leave to you:
   - **unresolved** (several legacy files declare the symbol, or none):
     read the candidates and copy the right one by hand.
   - **already_present** (the declaring file is in the new app, the symbol
     is not): the new copy was edited. Compare it with the legacy file and
     restore what was dropped.
   - **duplicates** (redeclaration, ambiguous type): usually a temporary
     copy (an extracted type, a shim, a placeholder) whose original has now
     arrived. Delete the temporary one and close its ledger row. If both are
     originals, they were duplicates in the legacy app too: keep the one the
     path map would produce.
   - **not_found assets**: the asset is generated from code or is new; list
     it, do not invent art.
   - Errors no script covers (API differences in the new app's own code,
     generics, access control): fix them in the new app's code, never in
     ported files, unless the ledger records why.
4. Stop and report if a round adds nothing and errors remain.

## 3. Shims and placeholders

The app should run early, long before every screen is ported:
- A route or tab whose screen is not ported yet renders a visible
  placeholder that names the legacy view (for example
  `NotPortedView("ProfileView")`). Each placeholder is a ledger row of kind
  `stub`, removed when the screen arrives.
- A missing dependency that would pull in a large unported area gets a
  minimal **shim** with the same API, recorded as `shim` with the condition
  that removes it. The duplicates report tells you when that condition is
  met.

Never comment out a call, delete a branch or return early to make ported
code compile; that silently drops behavior. Port the dependency or shim it,
and record it.

## 4. Verify

- Build green with the project's command; report the command and result.
- Run on a simulator **dedicated to this session** (create one with
  `xcrun simctl create` if another session or app uses the default one;
  sharing a simulator launched the wrong app in a real run). Hand the
  functional check to the user with a short list of what to try, derived
  from the flow specs' acceptance tests for the ported features.
- A debug-only entry point that exercises the core without UI (sign in, one
  list request, one realtime join) is worth adding before screens arrive;
  record it as a `stub` and keep it reachable only by a launch argument.

## 5. Ledger and report

Update `.migration/port/LEDGER.md` (or the new app's ledger if the project
keeps one there): rows opened (shims, stubs, gaps) and closed (removed when
originals arrived), each with its legacy and new location. Record where each
ported feature now lives (feature id → files) so parity can be checked
mechanically later.

In chat: what was ported, rounds needed, files and assets copied, shims and
placeholders left, exclusions, and the build result. Say plainly that the
UI is still the legacy styling and that `ui-port` is the next step.

## 6. Parity gate (after the last slice)

A green build proves that what was copied compiles, not that everything was
copied, and a restyle can drop a call while the file still builds. When the
user says the port is complete (and again after `ui-port`), check every
inventoried feature mechanically:

1. Write `.migration/parity/parity.config.json` for
   `${CLAUDE_PLUGIN_ROOT}/scripts/parity_check.py`: `legacy_src`, `new_src`,
   the inventory and enumerations from `feature-inventory`, the path map, one
   `symbols` entry per enumeration key (a `declared` and/or `used` regex), and
   `feature_fields` mapping inventory fields to those keys. Set `legacy_src`:
   symbols that were already dead in the legacy app are then reported as
   `inherited` instead of as gaps.
2. Run it: `python3 scripts/parity_check.py .migration/parity/parity.config.json --md .migration/parity/report.md`.
3. Read every gap in the legacy code before acting on it. `declared_unused`
   (still compiles, nothing calls it any more) is the most valuable finding:
   port the missing caller. A gap that is deliberate (deferred feature,
   replaced component, a symbol used only by deferred code) goes into `allow`
   with a reason the user can read; never allow a gap without reading it.
4. The gate is exit code 0. It checks presence, not behavior: wire-format and
   runtime defects still need the flow specs' acceptance tests and a run on
   the simulator.
