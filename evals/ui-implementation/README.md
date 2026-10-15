# Eval: UI implementation

Deterministic check for the gate of the
[UI Implementation](../../docs/workflows/ui-implementation.md) workflow,
`scripts/check_ds_usage.py`, on a synthetic fixture: the `paper-lantern`
contract and three screens.

```sh
evals/ui-implementation/run.sh            # must reproduce expected/ exactly
evals/ui-implementation/run.sh --update   # regenerate expected/ after an intended change
```

The fixture's Swift files are lint input, not a buildable app: `WalletCard`
references a style and a color that do not exist on purpose.

| Case | Expected |
|---|---|
| `ProfileHeaderView`: tokens only, `.display` outside a row, an SF Symbol sized with a literal, the generated pressable style | no findings |
| `DS.Gradients.dusk` declared in `extension DS.Gradients` in the project, not in the contract | accepted |
| `LeaderboardRowView`: `.display` (uses: hero) on a number in a row file | `row-text-style` error |
| The same number with `.fixedSize()` | `fixed-size-in-row` warning |
| `.padding(16)` / `spacing: 10` | token named (`DS.Spacing.md`) / off the scale |
| `.padding(.vertical, 1)` with `// ds-lint: allow literal-spacing <reason>` | suppressed |
| `WalletCard`: `.font(.headline)`, `.font(.system(size: 28))` on text, `.foregroundStyle(.blue)`, `Color(red:...)`, `cornerRadius: 14` | one finding each, by rule |
| `.dsFont(.huge)`, `DS.Colors.brandPink` | `unknown-token` errors |
| A rule's pattern inside a `//` comment | ignored |
| Errors present | exit code 1 |

## Judged checks (per real run, 0–2 each)

| Criterion | Question |
|---|---|
| Architecture fit | Does the screen follow the project's existing view / view model / navigation pattern, with no new one introduced? |
| Plan before code | Was the element → token / component map approved before implementation? |
| Shared components | Were existing shared components reused, and new ones added only when two screens needed them? |
| States | Are loading, empty, error, long-text and large-number states handled and previewed? |
| Gate honesty | Did the report give the check, build and screenshot results as they were, with suppressions listed with reasons? |
