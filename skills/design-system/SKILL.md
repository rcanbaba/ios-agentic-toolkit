---
name: design-system
description: Create an original, reusable iOS design system from reference screenshots (other apps or the user's own earlier app) plus the user's direction. Analyzes references, proposes directions, writes a validated design-system contract, generates SwiftUI tokens and a specimen, and renders it for review. Use when the user shares UI screenshots for inspiration, asks for a design language, theme, color palette or typography for an iOS/SwiftUI app, or says the generated UI looks generic.
argument-hint: "[screenshot paths and/or direction notes]"
allowed-tools: Read, Glob, Grep, Bash(swift *sample_colors.swift *), Bash(python3 *validate_design_system.py *), Bash(python3 *generate_swiftui.py *), Bash(*render_specimen.sh *), Bash(git check-ignore *)
---

# Design System

Turn references and direction into an **original** design system that a
SwiftUI project can use directly. The aim is a recognizable visual language,
not Apple's defaults and not a clone of any single reference.

Read the shared rules first: `${CLAUDE_PLUGIN_ROOT}/rules/ios-engineering.md`
(if not substituted, find `rules/ios-engineering.md` at the plugin root).
Tools live in `${CLAUDE_PLUGIN_ROOT}/scripts/`. The contract is
`${CLAUDE_PLUGIN_ROOT}/schemas/design-system.schema.json`; a complete example
is `${CLAUDE_PLUGIN_ROOT}/examples/design-systems/paper-lantern/`.

Input: $ARGUMENTS

## Modes

- **blend**: references from several apps. Take *traits* from each and combine
  them into something new. Never reproduce one reference wholesale.
- **evolve**: usually one app, often the user's own earlier app, plus the
  user's directives ("warmer", "less rounded", "more premium"). Keep what the
  user wants to keep, and transform the rest as directed.

Ask which mode applies if it is not obvious from the input.

## Working directory

Work in `.design-system/<name>/` in the current repository. Before writing,
check `git check-ignore -q .design-system/x`. If it is not ignored, append
`.design-system/` to `.git/info/exclude` (local only). Reference screenshots
and analysis notes stay there. Where the final contract and the generated
Swift files go in the project is decided with the user in step 5.

## 1. Analyze references (agentic + measured)

For each screenshot:
- Measure colors: `swift ${CLAUDE_PLUGIN_ROOT}/scripts/sample_colors.swift <images>`.
  Hex values come from this output, never from visual guessing. For small
  elements (a button, a tag), sample a cropped image of that region.
- Look at the image and describe its **signature**: what makes it
  recognizable. Consider:
  - type character: serif or sans, scale contrast, weights, tracking
  - color strategy: palette, usage ratio, where the accent appears, how
    surfaces layer, dark-mode behavior
  - shape language: radii, continuous vs circular corners, consistency
  - depth: shadows, borders, flat layers, blur
  - rhythm: spacing scale, density, alignment
  - component personality: buttons, cards, lists, navigation
- Values estimated by eye (spacing, radii, font sizes) must be labeled as
  estimates. Screenshot pixels are not points; use the sampler's
  `assumed_scale`.

Write `.design-system/<name>/references.md`: one section per reference with
its id (R1, R2, ...), measured colors and observed signature traits.

## 2. Propose directions → human decision

Propose **2–3 distinct directions**, or for *evolve* with clear directives,
one faithful interpretation plus one bolder alternative. For each direction:
- name and mood words
- which traits it takes from which reference (by id)
- palette sketch (hex), type pairing, shape and depth language
- what makes it different from a default SwiftUI app

Ask the questions only the user can answer (brand feelings, audience, things
to avoid). You may research current visual trends or typefaces if it helps,
but treat findings as suggestions.

**Stop and wait for the user's choice.** They may pick, mix, or redirect.

## 3. Write the contract

Write `.design-system/<name>/design-system.json`:
- `signature`: the 3–6 traits that make this system recognizable. If a
  trait is just an Apple default, it is not a signature trait.
- Colors need roles `background`, `surface`, `text_primary`,
  `text_secondary`, `accent` and `text_on_accent`, each with light and dark
  values. Record `origin`: sampled (with reference id), derived or chosen.
- Typography: prefer system families (`system_design`: default, rounded,
  serif, monospaced) or freely licensed fonts. A font seen in a screenshot
  may be commercial: propose a licensed alternative with similar character
  and record the license. Bundled fonts need PostScript names.
- Components: express each recipe only in tokens (primary/secondary button,
  card, tag, and whatever the app needs).
- `hig_deviations`: every deliberate departure from Apple defaults, with
  the reason. Free to change: color, type, shape, depth. Not negotiable:
  Dynamic Type support, 44pt tap targets, readable contrast.
- `estimates`: list every visually estimated value.

Validate: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_design_system.py <contract>`.
Fix all errors. Treat contrast warnings as design questions: either the
pair is only used for large/bold text (say so in `guidelines`), or the
color changes.

## 4. Generate, render, look

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/generate_swiftui.py <contract> --out .design-system/<name>/generated --check
${CLAUDE_PLUGIN_ROOT}/scripts/render_specimen.sh .design-system/<name>/generated .design-system/<name>/render [--fonts <dir>]
```

`--check` typechecks the output against the iOS Simulator SDK. The render
produces `specimen-light.png`, `specimen-dark.png` and
`specimen-large-type.png`. **Read the PNGs and critique them** against the
chosen direction and the references before showing the user:
- Does the signature come through, or does it still look like default iOS?
- Is the hierarchy clear? Do the components feel like one family?
- Does dark mode keep the character, or is it just inverted?
- Does large type still lay out acceptably?

Revise the contract and regenerate when the critique finds problems (at most
three rounds before asking the user). Never edit generated Swift files by
hand.

## 5. Human review → integrate

Show the user the specimen renders and a short summary: the signature, the
key tokens, HIG deviations, open estimates. Iterate on their feedback by
changing the contract.

When approved, ask where the contract and generated files belong in the
project (e.g. `DesignSystem/`), then copy them there. Check that the project
build includes them; with a folder-synced Xcode group this is automatic,
otherwise tell the user to add the files to the target. Do not edit
`project.pbxproj` without asking. Bundled fonts also need the font files in
the target and `UIAppFonts` in Info.plist; list these steps rather than doing
them silently.

Usage in code: `DS.Colors.<name>`, `DS.Spacing.<name>`, `DS.Shapes.<name>`,
`.dsFont(.<style>)`, `.dsComponent(DS.Components.<name>)`, and the
`DesignSystemSpecimen` view for previews.

## Boundaries

- No logos, brand marks, illustrations or proprietary icons from references.
- In *blend* mode the result must not be recognizable as one reference app.
- The generated code introduces tokens only; it does not restyle existing
  screens. Applying the system to screens is a separate task.
