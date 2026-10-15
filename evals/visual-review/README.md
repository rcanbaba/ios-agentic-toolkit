# Eval: visual review

Deterministic checks for the [Visual Review](../../docs/workflows/visual-review.md)
workflow on a synthetic fixture: the `paper-lantern` contract, two screens
drawn as flat color blocks by `make_screenshots.py`, the source of two views,
and a review written against them.

```sh
evals/visual-review/run.sh            # must reproduce expected/ and reject every negative case
evals/visual-review/run.sh --update   # regenerate expected/ after an intended change
```

| Case | Expected |
|---|---|
| Leaderboard screenshots in paper-lantern colors, with an ink/paper antialias blend | every palette cluster explained (by a token or a blend of two) |
| Wallet screenshot with a system blue band | `#007AFF` unexplained, exit code 1 |
| The views' code | the `check_ds_usage.py` report the review cites |
| `review.json`: a row style, an overflow at large type, an off-palette color, a quoted contract guideline, an accepted screen | valid; rendered to `review.md` by severity, per screen |

Negative cases (`negative_cases.py`), each rejected with its error: an
unknown rule id, an unknown lint rule, a guideline that is not in the
contract, DS-GUIDE without a quote, an unknown screen, a screenshot of
another screen, a missing screenshot file, a code line outside its file,
"seen" without a screenshot, a minor finding on an accepted screen, a
duplicate id.

## Judged checks (per real run, 0–2 each)

| Criterion | Question |
|---|---|
| Signal | Can the user see every finding in the cited screenshot? Were there no taste-only findings? |
| Calibration | Did screens the user accepted earlier get only blocker and major findings? |
| Fixability | Is each fix stated in design-system terms (a token, style or component)? |
| Siblings | Where a pattern repeats, are the other places named? |
| Independence | Did the reviewer work from screenshots and the contract rather than from the implementer's reasoning? |
| Read-only | Did the review change no app code? |
