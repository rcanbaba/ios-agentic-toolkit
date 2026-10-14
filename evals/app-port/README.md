# Eval: app port scripts

Deterministic checks for the scripts behind the [App Port](../../docs/workflows/app-port.md)
workflow, on a fully synthetic fixture (`fixture/`): a small legacy app, a new app that
has ported part of it, and a build log.

```sh
evals/app-port/run.sh            # must reproduce expected/ exactly and be idempotent
evals/app-port/run.sh --update   # regenerate expected/ after an intended change
```

What the fixture exercises, each a defect or trap seen in a real port:

| Case | Expected |
|---|---|
| `cannot find 'ProfileHeader'`, one declaring file | planned and copied to the mapped path |
| `value of type 'User' has no member 'isOnline'`, with an unrelated `struct ThreadPresence { var isOnline }` | only the `extension User` file is planned |
| `ImageResource has no member 'follow'` while a legacy class declares `func follow` | an asset member, never a code copy |
| `RowBadge` declared in two legacy files | unresolved, both candidates listed |
| `Tier` declared in a legacy file whose basename already exists in the new app | `already_present` (the new copy was edited) |
| `ChatTimeFormatter` and `FeedCountFormatter` declared in two legacy files both named `Formatters.swift` | the first planned; the second unresolved with the reason (one target cannot hold both), never dropped |
| `ChatRoute` ambiguous: an extracted copy and the arrived original | duplicates, both files listed |
| Asset sets `1x-boost`, `heroImage`, `brand-primary`, `tab-home` (string name) | matched as `_1XBoost`, `hero`, `brandPrimary`, `"tab-home"` |
| `AccentColor.colorset` in the legacy catalog | never copied |
| `chat-send` already in the new catalog | `already_in_target`, not copied |
| `missingArt` in the log, no such set | `not_found`, exit code 1 |
| Legacy styling in Profile and Chat, Wallet kept on purpose, design-system folder excluded; the config lives in `migration/port/` (as `.migration/port/` in a real project), outside the scanned sources | two groups, two balanced batches, Wallet reported as kept |
| Second run on the ported copy | nothing new planned or copied |
