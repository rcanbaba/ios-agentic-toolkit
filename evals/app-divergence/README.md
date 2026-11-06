# Eval: app divergence scripts

Deterministic checks for the scripts behind the [App Divergence](../../docs/workflows/app-divergence.md)
workflow, on a fully synthetic fixture (`fixture/`): a small music app (`original/`), the fork
ported from it (`fork/`, still identical in code, plus a xib, an Info.plist and an asset catalog),
rename maps that move the fork to its own vocabulary (Playlist → Mixtape, Track → Cut), and a file
split.

```sh
evals/app-divergence/run.sh            # must reproduce expected/ exactly
evals/app-divergence/run.sh --update   # regenerate expected/ after an intended change
```

What the fixture exercises, each a defect or trap seen in a real divergence:

| Case | Expected |
|---|---|
| `shuffle` → `play` in a file that already declares `play` | refused, nothing written |
| A map that renames the protected wire name `tracks`, gives a new name a banned word, renames a one-letter name | refused with all three reasons, nothing written |
| `Playlist` → `Mixtape` while the string `"[playlist] load failed"`, the key `"playlist.track_count"`, the CodingKeys raw values and the protected `playlistId` / `trackCount` / `tracks` stay | renamed in code, comments and interpolations only |
| Enum case `playlist` in a file that builds `"screen_" + String(describing: source)` | renamed, with a warning: the runtime text changes |
| Files and folders moved by hand to match (`Features/Playlist/PlaylistView.swift` → `Features/Mixtape/MixtapeView.swift`) | the verifier finds each baseline by reversing the map in the path; 0 problems |
| A "rename" that also edited a log string, renamed an unmapped local and added a line | `strings`, `string_multiset`, `tokens` and `lines` problems |
| xib `customClass="PlaylistCell"` and `NSClassFromString("PlaylistCell")` after the class became `MixtapeCell` | `class_not_declared` after the rename, not before; `ShimmerView` from another module skipped; `$(PRODUCT_MODULE_NAME).SceneDelegate` resolves |
| `UIImage(named: cond ? "Badges/gold" : "missing-art")`, a namespaced set, `Image("level_\(level)")`, `["eq_bass", "eq_treble", "eq_vocal"]` with `--asset-literals` | `missing-art`, the `level_` pattern and `eq_vocal` reported; `Badges/gold` resolves |
| Similarity of the renamed fork with its original | raw line overlap 60.9 %, normalized 100 %: the rename changed names, not logic; model fields as the largest matched kind after logic |
| A split of a view model into `+Queue` with one `private` dropped | 0 problems, `access_relaxed` 1 |
| A split that lost a method, changed a log string, added an import and a foreign extension | each reported |
