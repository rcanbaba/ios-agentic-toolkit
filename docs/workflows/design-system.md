# Workflow: Design System

**Status:** implemented · **Skill:** [`design-system`](../../skills/design-system/SKILL.md) · **Contract:** [`design-system.schema.json`](../../schemas/design-system.schema.json) · **Eval:** [`evals/design-system`](../../evals/design-system/README.md)

Creates an original, reusable design system for an iOS app from reference
screenshots (from other apps, or from the user's own earlier app) plus the
user's direction. The output is a validated contract, generated SwiftUI tokens,
and a rendered specimen.

## Why

When an agent builds a SwiftUI app without design input, it converges on
Apple's defaults: system font, standard sizes, ~10–12pt corner radii, blue
accent, grouped lists. The result is correct and forgettable. Asking for
"a unique design" does not fix this, because nothing concrete anchors the
choices.

This workflow anchors them. Concrete references supply real traits, the human
decides the direction, and a contract makes the result reusable. The contract
is consumed by generated code now, and by UI implementation later.

## In practice: Candy Sticker

From a real run for a new live-streaming app. Mode *blend*: five screenshots
from the team's earlier apps, plus directives: "white tones, a bit cartoon,
global audience, original, no 1:1 copy". The agent proposed three directions
(*Pastel Cloud*, *Candy Sticker*, *Comic Pop*); the human chose Candy Sticker.
After the specimen was approved, the agent built these sample screens from
the generated tokens:

| Profile | Messages | Explore | Daily reward | Live room |
|---|---|---|---|---|
| <img src="images/design-system/candy-sticker-profile.jpg" width="160"> | <img src="images/design-system/candy-sticker-messages.jpg" width="160"> | <img src="images/design-system/candy-sticker-explore.jpg" width="160"> | <img src="images/design-system/candy-sticker-bonus.jpg" width="160"> | <img src="images/design-system/candy-sticker-live.jpg" width="160"> |

The contract's `signature`, which is what keeps this from looking like a
default SwiftUI app:

- **Sticker depth:** white cards with a tinted outline and a short,
  unblurred offset shadow instead of blurred iOS shadows
- **Pressable candy buttons:** pink pills with a darker base, like a key
- **SF Rounded at heavy/black weights**, with large rounded numerals
- **Tilted sticker badges** (about −6°) for multipliers, levels and LIVE
- **Warm cream canvas** instead of grouped grey
- **Pink vs. sky-blue duel** that carries from the light app into the dark
  live stage

The first renders of this run exposed two renderer bugs (see
[Lessons](#lessons-from-real-use)).

## Architecture

```mermaid
flowchart TD
    IN["Reference screenshots<br/>+ direction notes"] --> M["sample_colors.swift<br/>measured hex · scale"]
    IN --> A["Reference analysis<br/>signature traits per reference (agentic)"]
    M --> A
    A --> D["2–3 directions<br/>(blend or evolve)"]
    D --> H1{"Human picks /<br/>mixes / redirects"}
    H1 --> C["design-system.json<br/>tokens · signature · components · HIG deviations"]
    C --> V{{"validate_design_system.py<br/>refs · names · WCAG contrast"}}
    V -- errors --> C
    V -- valid --> G["generate_swiftui.py --check<br/>DesignTokens.swift · DesignSystemSpecimen.swift"]
    G --> R["render_specimen.sh<br/>light · dark · large type PNGs"]
    R --> CR["Agent reads renders,<br/>critiques vs direction"]
    CR -- "off-direction (≤3 rounds)" --> C
    CR --> H2{"Human review"}
    H2 -- feedback --> C
    H2 -- approve --> P["Copy contract + generated<br/>files into the project"]
```

The render step closes the loop. The agent does not only write tokens; it
**looks at what the code actually draws** and revises. This is the visual
counterpart of build/test feedback in the crash workflow.

## Deterministic vs agentic responsibilities

| Responsibility | Approach |
|---|---|
| Color values from screenshots | **Deterministic** (`sample_colors.swift`: k-means, exact mode color per cluster) |
| Pixel → point scale | **Deterministic** (known iPhone widths) |
| Recognizing signature traits, naming a style | **Agentic** |
| Spacing, radii, font sizes from screenshots | **Agentic estimate**, labeled in `estimates` |
| Proposing directions, mixing traits | **Agentic** |
| Choosing the direction, approving the result | **Human** |
| Contract structure, token references, Swift-safe names | **Deterministic** (`validate_design_system.py`) |
| Text contrast in light and dark | **Deterministic** (WCAG ratio: <3:1 error, <4.5:1 warning) |
| SwiftUI tokens, Dynamic Type styles, component modifiers, specimen | **Deterministic codegen** (`generate_swiftui.py`) |
| Generated code compiles for iOS | **Deterministic** (`--check` typechecks against the Simulator SDK) |
| What the specimen looks like | **Deterministic render** (`render_specimen.sh`) + agentic critique |

The agent never types hex values from impressions or hand-writes token code.
Measured inputs and generated outputs keep the agentic part focused on
judgment.

## The contract

[`design-system.schema.json`](../../schemas/design-system.schema.json)
holds more than tokens, because tokens alone still produce generic UI:

| Section | Purpose |
|---|---|
| `direction` | Mode (blend/evolve), human directives, mood, why this direction |
| `references` | Which traits were taken from which reference |
| `signature` | The few traits that make the system recognizable |
| `colors` | Semantic roles, light/dark values, origin (sampled/derived/chosen) |
| `typography` | Families with licenses; styles bound to Dynamic Type text styles, with the `uses` each style is allowed in (1.1) |
| `spacing`, `radii`, `shadows`, `borders` | Token scales |
| `gradients`, `overlays` | Gradients and translucent layers (dimming) composed from color tokens (1.1) |
| `components` | Recipes expressed only in tokens; optional `pressed` state (1.1) |
| `guidelines` | Do / don't rules for implementation |
| `hig_deviations` | Deliberate departures from Apple defaults, with reasons |
| `estimates` | Every value estimated by eye rather than measured |

## Generated SwiftUI

```swift
Text("Continue")
    .dsComponent(DS.Components.primaryButton)

VStack(spacing: DS.Spacing.md) {
    Text(title).dsFont(.headline)          // scales with Dynamic Type
    Text(body).dsFont(.body)
        .foregroundStyle(DS.Colors.inkMuted)
}
.padding(DS.Spacing.md)
.background(DS.Colors.card, in: DS.Shapes.crisp)
```

Colors are dynamic (light/dark) without an asset catalog. Text styles scale
with `@ScaledMetric` relative to a system text style. `DesignSystemSpecimen`
has Light, Dark and Large-type previews in Xcode.

## Human in the loop

| Decision | Who |
|---|---|
| Mode and references | Human provides |
| Direction among 2–3 options | **Human** |
| Contrast warnings: change color or restrict usage | Agent proposes, human confirms |
| Final approval after seeing renders | **Human** |
| Where files go in the project, project-file changes | **Human** |

## Example contract

The real run's contract stays in its project. The repository's complete,
regenerable example is
[`examples/design-systems/paper-lantern`](../../examples/design-systems/paper-lantern),
a synthetic *blend* of three references: a warm editorial system with
serif display type, paper surfaces, a single vermilion accent and hairline
depth.

| Light | Dark |
|---|---|
| <img src="../../examples/design-systems/paper-lantern/render/specimen-light.png" width="260"> | <img src="../../examples/design-systems/paper-lantern/render/specimen-dark.png" width="260"> |

The renders were checked round-trip: sampling them with `sample_colors.swift`
returns the contract's exact hex values in both modes.

## Design decisions

- **Contract first, code generated.** The contract is reviewable, diffable
  and reusable by later workflows (UI implementation, visual review).
  Generated code is never edited by hand, so the two cannot drift.
- **Render instead of describing.** The agent reads PNG renders of the
  specimen. A design cannot be judged from a JSON file, and neither can
  the agent judge one.
- **SwiftUI specimen, not HTML.** An HTML page cannot reproduce SF fonts,
  continuous corners or dynamic colors faithfully. The render runs the real
  generated code on the iOS Simulator.
- **No Xcode project for rendering.** `render_specimen.sh` compiles a tiny
  app with `swiftc` and installs it on a simulator. It has no dependencies
  and touches nothing in the user's project.
- **No subagent yet.** Analyzing up to ten screenshots in one context is
  manageable. Per-reference analysis in isolated subagents is the first
  candidate if context becomes a problem in real use.
- **Accessibility is not negotiable.** Contrast is checked mechanically,
  text styles scale with Dynamic Type, and component recipes warn below
  44pt.

## Lessons from real use

| Observed in a real run | Change |
|---|---|
| A hard shadow (`radius: 0`) drew a second copy of the component's text: the shadow was applied to the composited view, not the shape. Soft shadows hid it, but even the example had a faint blur under the text | Shadows apply only to the background shape, in components and the specimen |
| A large system (20 colors, 9 type styles, 8 components) exceeded ImageRenderer's ~8192px limit, and the script failed with a bare `cp` error | Height is measured with the same renderer at a tiny scale; tall specimens are rendered as tiles at full scale; failures are reported and partial results kept |
| While fixing the above, a pixel comparison showed that the old large-type render had compressed and truncated text and transparent areas | Content is rendered at its natural height (`fixedSize`), never a forced one; verified pixel-identical for light/dark, corrected for large type |

| The specimen shows tokens, but the human judged the system from sample screens. The agent rendered them with a copy of the specimen renderer | Not built yet. Candidate: a `showcase` step that renders agent-written sample screens with the same renderer |
| The contract has no gradients or component variants, so the agent added them in a hand-written extras file next to the generated code | Contract 1.1: `gradients` and `overlays` are tokens; `DSComponent.with(...)` is generated. Needed again by the port that followed, which used them throughout |
| In the port that followed, a pressable button style and the popup dimming were written by hand, and each screen chose its own press feedback | Components declare a `pressed` state; `DSPressableButtonStyle` is generated |
| The screenshot review of the port found display-size numbers (22pt+) in list rows and a list row overflowing the screen width. Nothing in the contract said which style belongs in a row | Text styles declare `uses`; the validator warns on row styles above 20pt; the specimen renders dense rows with a long name and a large number, in light, dark and large type |

Lesson for the workflow itself: a renderer that distorts layout gives the
agent wrong visual feedback. Renderer changes are verified by pixel
comparison against a known-good render, not by "it produced a PNG".
