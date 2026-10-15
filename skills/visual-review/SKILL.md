---
name: visual-review
description: Review implemented iOS screens against the design-system contract and mobile UX rules from simulator screenshots, read-only. Captures each screen in light, dark and large text, gathers deterministic evidence (token-usage lint, palette check), has an independent reviewer write findings tied to a rule and to a screenshot, validates them, and hands the user a short triage list; approved fixes go back to ui-implement. Use when the user asks to review, audit or polish the UI of screens, or after ui-implement or ui-port finishes a batch.
argument-hint: "<screens to review> [how to open each: launch argument or deep link] [screens already accepted]"
allowed-tools: Read, Glob, Grep, Write, Agent, Bash(*capture_screens.sh *), Bash(swift *sample_colors.swift *), Bash(python3 *palette_check.py *), Bash(python3 *check_ds_usage.py *), Bash(python3 *validate_visual_review.py *), Bash(xcrun simctl *), Bash(git check-ignore *)
---

# Visual Review

Look at what the screens actually draw and report where they leave the
design system or basic mobile UX. The review is **read-only**: it never edits
app code. Its output is a short, validated list the user triages; fixes go
through `ui-implement` (or `ui-port`'s review loop) after the user picks them.

A useful review is short. In the real run this workflow was derived from,
most screens were fine and the user's corrections came down to a few patterns
(display-size numbers in rows, a row overflowing the screen width, text sized
for a different surface). A review that lists forty taste notes buries those.
Report what can be pointed at in a screenshot, cite a rule, and stop.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Rules for findings: `ux-rules.md` next to this file. Reviewer prompt:
`review-agent-prompt.md`. Contract:
`${CLAUDE_PLUGIN_ROOT}/schemas/visual-review.schema.json`.

Input: $ARGUMENTS

## Working directory

Work in `.visual-review/<run>/` in the target repository (screenshots,
reports, `review.json`, `review.md`). Check
`git check-ignore -q .visual-review/x`; if it is not ignored, append
`.visual-review/` to `.git/info/exclude`.

## 1. Scope → human confirms

List the screens to review and how to open each one (a debug launch argument,
a deep link, or navigation steps the user performs), and which screens the
user has **already accepted**. For accepted screens only blockers and major
issues are reported. Ask for anything that is not clear; do not review the
whole app by default.

## 2. Capture

On the session's simulator (find the project's dedicated one in its
CLAUDE.md; never boot another without asking):

```
${CLAUDE_PLUGIN_ROOT}/scripts/capture_screens.sh <udid> <bundle-id> .visual-review/<run>/screenshots <screen> [--variants light,dark,large-type] [-- <launch args>]
```

Skip `dark` when the app is light-only (say so in `not_checked`). Screens that
need navigation are captured with `xcrun simctl io <udid> screenshot <file>`
while the user drives the app. Capture each important state (empty, error,
long content) the user can reach. Open every screenshot and check that it
shows the intended screen before using it.

## 3. Deterministic evidence

- Token usage on the screens' files:
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_ds_usage.py <contract> <files> --out .visual-review/<run>/reports/ds-usage.json`
- Palette, per appearance:
  `swift ${CLAUDE_PLUGIN_ROOT}/scripts/sample_colors.swift <light screenshots> > .../reports/samples-light.json`, then
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/palette_check.py <contract> .../reports/samples-light.json --out .../reports/palette-light.json`
  (`--appearance dark` for dark screenshots; `--ignore '#000000'` for the
  Dynamic Island in full-screen captures). An unexplained cluster is a lead,
  not a finding: photos, avatars and video are content.

## 4. Independent review

Spawn one reviewer agent with `review-agent-prompt.md` filled in: the
screenshots, the contract, `ux-rules.md`, the reports, the accepted screens,
and the source files (for code evidence only). It does not see this
conversation's reasoning about how the screens were built, so it judges what
is drawn, not what was intended. For more than about ten screens, split them
between two or three reviewers by feature.

Validate what it writes:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_visual_review.py .visual-review/<run>/review.json --src <app root> --md .visual-review/<run>/review.md
```

Fix the review until it is valid. A rejected finding (no screenshot shows it,
a guideline that is not in the contract) is dropped or downgraded to
`inferred`, never rewritten to pass.

## 5. Look yourself, then triage with the user

Open the screenshot behind every blocker and major finding and confirm it.
Then give the user `review.md`: counts by severity, then per screen the
findings with their fix in design-system terms and the sibling places where
the same pattern probably exists. The user marks each finding `fix` or
`skip`; record the decisions in `review.json`.

## 6. Feed back

Approved fixes go to `ui-implement` (new screens) or `ui-port`'s review loop
(ported screens), as one list grouped by pattern, with the siblings, so a fix
is applied everywhere at once. After the fix, re-capture only the affected
screens and re-run steps 3–5 for them. A finding is closed when its
screenshot no longer shows it.
