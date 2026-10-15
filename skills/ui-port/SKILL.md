---
name: ui-port
description: Rebuild the view layer of screens that were ported verbatim from a legacy iOS app on the new app's design system, with parallel restyle agents that change only styling and layout. Measures the legacy styling left, partitions it into feature batches, writes the port rules, runs the agents, integrates and gates on a green build and an empty legacy-styling report, then hands a visual review list to the user. Use after port-code, when ported screens still look like the old app.
argument-hint: "[folders to restyle, or 'all'] [design system folder]"
allowed-tools: Read, Glob, Grep, Edit, Write, Agent, Bash(python3 *find_legacy_styling.py *), Bash(xcodebuild *), Bash(xcrun simctl *)
---

# UI Port

Ported screens keep the legacy app's view models and behavior; this skill
rebuilds only how they look. The design system (from the `design-system`
skill or the project's own) is the target language. In the run this was
derived from, six parallel agents restyled about 300 screen files in one
pass; the integrator fixed one typo, and every later fix came from the
user's screenshot review, which is why that review is a stage, not an
afterthought.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Templates next to this file: `port-rules-template.md`,
`restyle-agent-prompt.md`. Script:
`${CLAUDE_PLUGIN_ROOT}/scripts/find_legacy_styling.py`.

Input: $ARGUMENTS

## Prerequisites

- The screens are ported and the app builds (`port-code`).
- The design system is in the project: tokens, components and its written
  guide (for a generated one, `DESIGN_SYSTEM.md`, `DesignTokens.swift` and
  the specimen renders).
- Behavior changes are not part of this skill. Anything that looks wrong in
  legacy behavior is listed for the user, never fixed on the way.

## 1. Measure → human confirms the batches

1. Write `.migration/port/styling.config.json` for
   `find_legacy_styling.py` (`src` relative to the config, for example
   `../../App`): the legacy styling forms (the old font and
   color helpers, named colors, legacy gradient and radius tokens, legacy
   art via `Image(.x)` / `UIImage(named:)`), `exclude` for the design system
   folder and generated code, and `keep` for areas deferred on purpose
   (each with its reason). Read the legacy app's design layer to find the
   forms; do not guess them.
2. Run it with `--batches N` (N ≤ 8):
   `python3 scripts/find_legacy_styling.py .migration/port/styling.config.json --batches 6`
3. Propose the batches. The script balances by lines; adjust so each batch
   is a **family of surfaces** an agent can style consistently (profile and
   its sub-screens; chat, DM and media viewer; calls and overlays), and so
   shared components land in exactly one batch. **Wait for the user to
   confirm** the batches and the deferred areas.

## 2. Reference screens first

Before any agent runs, the integrator restyles one or two representative
screens itself (a list with cards, a form, a popup) and the user approves
them on the simulator. Agents imitate approved code far better than they
follow prose. List these files as the examples in the rules. Reusable
pieces created here (a popup card, a pressable button style, an input
field) go into the shared UI folder so every agent uses the same ones.

## 3. Port rules

Fill `port-rules-template.md` into a project file (for example
`Porting/UI_PORT_RULES.md`): paths, the design system's token and component
names, which surfaces are light screens and which sit over media, the
reference screens, the visual references per batch, and the art kept for a
later redraw. Every agent reads the same file, so a correction is made once.

## 4. Restyle agents

Spawn one agent per batch, in parallel, with `restyle-agent-prompt.md`
filled in. Each agent:
- owns its folders and edits nothing else;
- changes only styling and layout, never logic, API, bindings, callbacks,
  timers, localization keys or analytics;
- does not build (parallel builds of one project collide); a syntax-only
  `swiftc -parse` on its files is allowed;
- returns the report the prompt defines: files changed, what it could not
  convert (with `file:line`), additive API changes, and every behavior or
  design choice it was unsure about.

## 5. Integrate and gate

1. Build with the project's command and fix integration errors (usually
   typos or a helper two agents both needed).
2. Re-run `find_legacy_styling.py` without `--batches`. The gate is zero
   matches outside `keep`; anything left is either converted now or added to
   `keep` with a reason the user can see.
3. Merge the agents' "unsure" lists into one **review list** for the user,
   grouped by screen: design choices made on their behalf (a second primary
   action demoted to secondary, art replaced by a symbol, a layout reordered)
   and legacy quirks noticed (an inverted icon, a value shown in the wrong
   row). Quirks are not fixed until the user says so; record the decision.
4. Install on the session's own simulator and give the user the review list
   with where to look.

## 6. Review loop

The user reviews on the simulator and sends screenshots. Fix what they point
out, then search for the same pattern elsewhere before rebuilding: a defect
seen on one screen usually exists in its siblings (text colored for a dark
surface rendered on a light sheet; a display-size number in a dense row).
Repeat until the user accepts the batch.

Product art the legacy app drew as bitmaps (tier badges, level badges, frames,
rank medals) is kept during restyle and redrawn afterwards **as one set by one
owner**, so the set stays consistent; agents only note where it appears.

## 7. Ledger and report

Record in the ledger: batches done, kept areas and why, shared components
added, art kept for the redraw, quirks found and their decisions. In chat:
the gate result, the build result, the review list, and what is still legacy.
When the last batch is accepted, re-run the `port-code` parity gate
(`scripts/parity_check.py`): a restyle can drop a call while the file still
builds, and the gate reports it as `declared_unused`.
