# Feature Inventory Evaluation

The question is whether the inventory is **complete, exact and verified**,
not whether it reads well. Completeness is measured against a deterministic
baseline extracted from code, so most of this rubric is scripted.

## Deterministic checks (scripted)

| Check | Pass condition |
|---|---|
| Baseline | `extract_enumerations.py` reports nothing "not found"; method count matches a manual count of the API client (including internal and extension methods) |
| Parts | every part passes `validate_inventory_part.py` |
| Coverage | `coverage.json`: all source files covered; no unknown identifiers; no dangling `depends_on`; no duplicate ids; no core/high feature without a flow; unreferenced identifiers are exactly the `dead_identifiers` of `reconciliation.json` |
| Reconciliation | no `ambiguous` and no `unresolved_depends_on` left, or each one resolved by a recorded override or patch |
| Verification | every core/high feature is in at least one scope; every verification file passes `apply_verification.py --dry-run`; no `appended_instead_of_replace` left unresolved in `applied.json` |
| Read-only | `git status` shows no change outside `.migration/` |

## Judged checks (human or model grader, 0–2 each)

| Criterion | Question |
|---|---|
| Granularity | Is one feature one user-recognizable capability, neither "Room" nor one feature per function? |
| Flow fidelity | Do core flows match the code step by step, including failure and interruption? |
| Actions | Are secondary, long-press, menu and sheet actions listed, not only primary buttons? |
| As-is discipline | Is everything described as current behavior, with opinions confined to `known_issues` and `open_questions`? |
| Verification independence | Did verifiers correct against code, with file:line evidence, rather than restate the inventory? |
| Reconciliation judgment | Were ambiguous attachments resolved by reading the call site, not by attaching everywhere? |
| Hunter sweep | Did the missing-feature hunter report what it swept, so that "nothing missing" is credible? |
| Honesty | Are open questions real unknowns rather than things the agent could have read? |

## Planned fixtures

| Case | What it tests |
|---|---|
| [`examples/migrations/pocket-threads`](../../examples/migrations/pocket-threads) | End-to-end pipeline on a tiny synthetic app: call-site attachment, dangling id resolution, dead identifiers, patch application, false-positive annotation, missing feature |
| API client with methods in extensions and without access modifiers | Baseline includes internal methods |
| Sub-route names that collide with ordinary identifiers | Call-site patterns must match the navigation form, not a bare name |
| One file shared by several features | Reconciliation reports ambiguity instead of over-attributing |
| Verifier that rewrites a flow as one step | `replace` without `old` is rejected; the flow keeps its steps |
| Two verifiers disagreeing on one feature | The orchestrator decides by direct code read and records it |

## Running

Not automated yet. For the scripts: copy the example, replace
`inventory/parts/` with `inventory/parts.as-authored/`, delete
`reconciliation.json` and `applied.json`, run extract → merge → reconcile →
merge → apply → reconcile → merge → render, and `diff -r` against the
checked-in example; the result must be identical, and a second run must
change nothing. Score agent runs on a real repository with the rubric above.
