# Design System Evaluation

Design quality is partly subjective, so the evaluation separates what can be
checked mechanically from what needs judgment. The question is not whether
the result is pretty. It is whether the system is **original, faithful to the
chosen direction, coherent and usable**.

## Deterministic checks (scripted)

| Check | Pass condition |
|---|---|
| Contract | `validate_design_system.py` reports no errors |
| Measured colors | Every `sampled` color matches `sample_colors.swift` output for its reference (±2 per channel) |
| Code | `generate_swiftui.py --check` typechecks |
| Render | `render_specimen.sh` produces light, dark and large-type PNGs |
| Round trip | Sampling the renders returns the contract's background and surface colors exactly |
| Project safety | Nothing outside `.design-system/` changes before the human approves integration |

## Judged checks (human or model grader, 0–2 each)

| Criterion | Question |
|---|---|
| Originality | Would someone recognize it as distinct from a default SwiftUI app? In *blend* mode, is it not recognizable as any single reference? |
| Signature | Are the signature traits real differentiators, and visible in the specimen? |
| Direction fidelity | Does the result match the chosen direction and the user's directives? |
| Reference use | Are traits attributed correctly to references; were measured values used rather than guesses? |
| Coherence | Do components, type and color feel like one family, in light and dark? |
| Dark mode | Does dark mode keep the character rather than simply inverting? |
| Honesty | Are estimates, HIG deviations and font licenses stated? |
| Process | Did it stop for the human's direction choice instead of picking one silently? |

## Planned fixtures

| Case | What it tests |
|---|---|
| Blend of three distinct apps | Combines traits without cloning one |
| Evolve own app: "warmer, less rounded" | Keeps identity, applies directives precisely |
| References using a commercial font | Proposes a licensed alternative and records the license |
| Low-contrast reference palette | Fixes contrast without losing the palette's character |
| Single reference, no directives | Asks for direction instead of copying |
| Dark-only references | Derives a credible light mode (or asks) |
