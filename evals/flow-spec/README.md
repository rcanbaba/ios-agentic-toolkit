# Flow Spec Evaluation

A flow spec is judged by whether a new app could be built and tested from it
**without reading the old code**, and by whether it keeps as-is behavior
apart from target decisions.

## Deterministic checks (scripted)

| Check | Pass condition |
|---|---|
| Contract | `validate_flow_spec.py` reports no errors |
| Identifier completeness | every api / realtime identifier of the related features is in the spec or excluded with a reason |
| Reachability | every state reachable from the entry states; no event unused (warning) |
| Evidence | every `file:line` resolves to an existing file and lines inside it |
| Test coverage | `covers` includes `happy_path`, every `INV-`, `INT-` and `FH-` id (`behavior` for other tests) |
| Spec coverage | `merge_inventory.py --coverage-only` passes: every core/high feature is in a spec or has a `spec_note` |
| Decisions | after step 4, `--require-decisions` passes, every decision is in `DECISIONS.md`, "align with the old app" decisions cite code that was read, and `render_pending.py` lists no decided question |
| Audit | `AUDIT.md` exists; no `data-loss` or `wrong` finding is still open |
| Read-only | `git status` shows no change outside `.migration/` |

## Judged checks (human or model grader, 0–2 each)

| Criterion | Question |
|---|---|
| Evidence | Does each transition's `file:line` actually show that transition? |
| Interruptions | Are background, network loss, reconnect, app kill, concurrent flow, expiry and permission loss all covered with current behavior, even when it is "nothing happens"? |
| Resources | Do states say what is held (channels, subscriptions, timers, capture) so cleanup can be checked? |
| As-is discipline | Is target behavior confined to `open_decisions`? Are `as_is_bugs` observations with impact? |
| Exclusions | Are excluded identifiers genuinely outside the flow? |
| Cross-flow | Are interactions with other sessions and flows described? |
| Decision grouping | Were recurring questions grouped into cross-cutting rules decided once, with a default rule for the rest? |
| Spec notes | Does each `spec_note` hold up, or is a critical flow being skipped? |
| Audit depth | Did the audit sample claims against code and read the scripts' logs, and does it say what it sampled? |
| Tests | Would the acceptance tests fail on an implementation that skips cleanup or mishandles a failure? |

## Planned fixtures

| Case | What it tests |
|---|---|
| [`examples/migrations/pocket-threads`](../../examples/migrations/pocket-threads) `send-message` | Validator, renderer, exclusions, decided and deferred decisions |
| Flow with a shared teardown used by several exit paths | Invariant and `*` transitions, not one transition per exit |
| Two flows sharing a reconnect handler | Specs agree; the orchestrator resolves conflicts by code read |
| Flow whose related features list an unused identifier | Honest exclusion with reason |
| Spec with "should" language in transitions | Fails the as-is criterion |

## Running

The scripted checks run as part of the feature-inventory replay and negative
cases (see [`evals/feature-inventory`](../feature-inventory/README.md#running)),
which include the flow-spec validator, renderer and `render_pending.py`.
Score agent-written specs on a real repository with the rubric above.
