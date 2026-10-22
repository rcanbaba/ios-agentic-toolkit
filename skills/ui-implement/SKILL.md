---
name: ui-implement
description: Implement new SwiftUI screens or components on the project's design system (a design-system contract with generated tokens), inside the existing architecture. Maps every element to tokens and components in a plan the user approves, reuses shared components, writes the views with all their states, then gates on check_ds_usage.py, the build and simulator screenshots. Use when the user asks to build a new screen, sheet, row or component in an app that has a design system, or to rebuild one screen from a spec or mockup.
argument-hint: "<screen or component to build> [spec, mockup or legacy screen] [target folder]"
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(python3 *check_ds_usage.py *), Bash(python3 *validate_design_system.py *), Bash(xcodebuild *), Bash(xcrun simctl *), Bash(git status*), Bash(git diff*)
---

# UI Implementation

Build screens that look like the design system and behave like the rest of
the app. The design system decides how things look (the contract, the
generated tokens and the project's guide); the project decides how things are
wired (its view, view model, navigation and dependency patterns). This skill
adds nothing to either: it uses them.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Gate script: `${CLAUDE_PLUGIN_ROOT}/scripts/check_ds_usage.py`.

Input: $ARGUMENTS

## 1. Read the two contracts

1. **Design system.** Find the contract (`design-system.json`), the generated
   tokens (`DesignTokens.swift`), the project's guide (for example
   `DESIGN_SYSTEM.md`) and any hand-written additions (`extension DS`).
   Validate the contract with `validate_design_system.py`. Note for each text
   style its `uses`; for each component whether it has a `pressed` state.
2. **Shared components.** List what already exists (search for
   `.dsComponent(`, `ButtonStyle`, `ViewModifier` and the shared UI folder):
   popup card, input field, avatar, badges, empty state, loading. A new screen
   reuses these; it does not draw its own.
3. **Architecture.** Pick the closest existing screen as the template: how
   its view model is created and owned, how it navigates and presents, how it
   loads data and shows errors, how it is localized and tracked. Follow it.
   Do not introduce a new pattern unless the user asks.

## 2. Plan → human approval

Before writing code, give the user a short plan:

- **Surface:** light screen, sheet, or over media (a dark stage, video).
  Text and icon colors follow from it.
- **Element map:** every element of the screen → a token or component.
  Text: the style, checked against its `uses` (rows get row styles; one
  `hero` per screen). Buttons: which component and button style; at most one
  primary action per screen.
- **States:** loading, empty, error, and the content extremes: the longest
  name, the largest number, missing images, right-to-left if supported.
- **New shared components**, only when two screens need them, built from
  tokens and placed in the shared UI folder.
- **What the contract lacks**, if anything (a color, a gradient, a component
  recipe): propose adding it to the contract and regenerating, not a local
  literal.

**Wait for approval.** For a single small component, a one-paragraph plan is
enough, but it is still shown first.

## 3. Implement

- Tokens only: `DS.Colors`, `DS.Spacing`, `DS.Shapes`, `DS.Gradients`,
  `DS.Overlays`, `.dsFont`, `.dsComponent`, `DSPressableButtonStyle`. A
  literal is allowed only with `// ds-lint: allow <rule> <reason>`, and every
  one is listed in the report.
- Rows and dense layouts: names `.lineLimit(1)` and truncate; numbers
  `.monospacedDigit()` and may scale down (`minimumScaleFactor`) but are
  never `.fixedSize()`; trailing content gets layout priority instead.
- Tap targets at least 44pt; icon-only buttons get an accessibility label.
- Text scales with Dynamic Type (`.dsFont` does); fixed heights only on art.
- Behavior wiring, localization keys, analytics and navigation follow the
  template screen. Nothing is invented: unknown copy, actions or data are
  asked for.
- Add `#Preview`s for the states from the plan, with long-content fixtures.

## 4. Gate

1. `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/check_ds_usage.py <contract> <changed files or folders> --exclude '<generated folder>/*'`.
   Zero errors. Warnings are fixed or suppressed with a reason. Name row
   files `...Row`, `...Cell` or `...Item` (or pass `--row-files`) so the row
   rules apply.
2. Build with the project's command (its CLAUDE.md or README). Fix and repeat.
3. Run on the session's simulator and take screenshots of each state:
   `xcrun simctl io <udid> screenshot <file>`. Also take one at a large text
   size (`xcrun simctl ui <udid> content_size extra-extra-extra-large`, reset
   afterwards) and, if the app supports it, in dark appearance. Look at every
   screenshot: overflow past the screen edge, truncated numbers, text colored
   for the wrong surface, crowded rows.

## 5. Report

The files added and changed, shared components added, contract changes
proposed, suppressions with their reasons, the check and build results, and
the screenshots with what was checked in each. Say what was not verified
(for example, a state that needs backend data). Do not commit unless the
user asks.
