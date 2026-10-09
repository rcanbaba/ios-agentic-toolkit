# Crash Analysis Evaluation

Agentic workflows should be judged by repeatable evaluation, not by a good demo.
This document defines how the `crash-analysis` skill is evaluated. V1 is a
rubric plus a fixture plan; fixtures are added as real usage reveals failure
modes worth guarding against.

## What is being evaluated

The quality of the **investigation and its conclusions**, not whether a fix is
produced. A run that answers "insufficient evidence" on an ambiguous crash
scores higher than one that invents a confident root cause.

## Fixture format

Each fixture is a synthetic, self-contained case, like
[`examples/crashes/player-quality-nil-engine`](../../examples/crashes/player-quality-nil-engine):

- `crashlytics-report.md`: the input as an engineer would paste it
- `source/`: a minimal synthetic code base containing the crash site, plus
  distractors where useful
- an expected-outcome note: correct component, acceptable root-cause
  categories, acceptable verdicts, and things the run must not do

## Rubric

Deterministic checks (scripted):

| Check | Pass condition |
|---|---|
| Contract | `analysis.json` passes `scripts/validate_analysis.py` |
| Read-only | no files outside `.crash-analysis/` changed (`git status`) |
| Gate respected | `code_change.justified` is false when the expected verdict is `insufficient_evidence` |

Judged checks (human or model grader, 0–2 each):

| Criterion | Question |
|---|---|
| Component | Did it identify the correct component / first meaningful app frame? |
| Investigation | Did it read the code that matters (crash site, relevant caller or lifecycle owner), and avoid reading unrelated code? |
| Evidence discipline | Are evidence items actual observations, separated from inference? |
| Calibration | Is the confidence justified? No overclaiming; "confirmed" only with reproduction or unambiguous code. |
| Root-cause family | Is the leading hypothesis's category reasonable for the expected outcome? |
| Alternatives | Were plausible alternatives considered and argued against with evidence? |
| Verification | Is the suggested reproduction/verification strategy appropriate? |

## Planned fixtures

| Case | What it tests |
|---|---|
| Obvious force unwrap | Baseline: finds the site, does not overcomplicate |
| Out-of-bounds access | Traces the index source rather than adding a bounds check |
| SDK lifecycle misuse | Blames app usage, not the SDK; no version bump |
| Main-thread violation | Reads the callback's delivery queue |
| Object lifetime (`EXC_BAD_ACCESS`) | Looks for unowned/unsafe references and outliving callbacks |
| Misleading top frame | Ignores the system top frame, finds the app frame below |
| Ambiguous native crash | Expected verdict: `insufficient_evidence` with useful missing-information |
| Insufficient evidence | Truncated stack, no breadcrumbs: must not propose a code change |

## Running

Not automated yet. Claude Code's native `claude plugin eval` (cases under
`evals/` with prompt + graders) is the intended runner once there are enough
fixtures to make automation worth it. Until then, run the skill on a fixture
in a scratch copy and score it with the rubric above.
