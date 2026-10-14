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
| Evidence | every core/high flow step carries `file:line` that resolves to an existing file and lines inside it |
| Verification | every core/high feature is in at least one scope; every verification file passes `apply_verification.py --dry-run`; `applied.json` has no `skipped` and no `annotate_unmatched` left |
| Text coverage | every unreferenced informational name (unconsumed messages, API paths without a feature, SDKs) was looked at |
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

## Fixtures

| Case | What it tests | Status |
|---|---|---|
| [`examples/migrations/pocket-threads`](../../examples/migrations/pocket-threads) | End-to-end pipeline on a tiny synthetic app: call-site attachment, dangling id resolution, dead identifiers, unconsumed messages, excluded helpers, note normalization, patch application, false-positive annotation, missing feature, spec notes | `replay.sh` |
| API client with methods in extensions, without access modifiers, and with multi-line requests | Baseline includes internal methods and their paths | example + `negative_cases.py` |
| Route names that collide with SwiftUI tokens | Bare route patterns are refused | `negative_cases.py` |
| An identifier called from the files of several features | Reconciliation reports ambiguity instead of over-attributing | `negative_cases.py` |
| Verifier that rewrites a flow as one step, or a replace that matches nothing | Nothing changes; the patch is listed for review | `negative_cases.py` |
| Two verifiers disagreeing on one feature | The orchestrator decides by direct code read and records it | planned |
| SDK delegate callbacks against a pod header; dependencies; plist, string and notification keys | New extractor kinds | `negative_cases.py` (builds its own fixture) |

## Running

The deterministic part is automated:

```sh
evals/feature-inventory/replay.sh                    # [--update] after an intended change
python3 evals/feature-inventory/negative_cases.py
```

`replay.sh` resets a copy of the example to the parts as the area agents
wrote them and runs the whole pipeline (extract → merge → reconcile → merge
→ apply → reconcile → merge → render → flow-spec validate/render → pending →
coverage-only). The result must equal the checked-in example, and a second
run must change nothing.

`negative_cases.py` breaks a fresh copy in one way per case and checks that
the scripts refuse or report it: replace without a unique match, joined,
unknown or prefixed identifiers, flow steps without resolvable evidence,
`REPLACES` source-file patches, unmatched known-issue verdicts, bare route
patterns, identifiers shared by more than two features, lossy duplicate
merges, spec evidence outside a file, unreachable states, uncovered
invariants, blank exclusion reasons, undocumented "align with the legacy
app" decisions, re-listed decided questions, and enum parsing. Every case
comes from a defect seen in a real run, and each one fails on the scripts
before the fix.

Score agent runs on a real repository with the rubric above.
