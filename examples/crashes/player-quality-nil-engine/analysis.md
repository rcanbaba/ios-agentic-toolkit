# Crash analysis: player-quality-nil-engine

> Example output of the `crash-analysis` skill for the synthetic input in
> `crashlytics-report.md`. Machine-readable form: `analysis.json`.

## Summary
Dismissing the stream-quality sheet after the app returns from background calls
`PlayerSession.applyQuality(_:)`, which implicitly unwraps an engine that was
released when the app entered background.

## Impact
1,284 events / 911 users in 7 days, 3.4.0 and 3.4.1, all OS versions and
devices, foreground. **Severity: high.**

## Crash location
Main thread. Top frame `libswiftCore _assertionFailure` (symptom);
first app frame `PlayerSession.applyQuality(_:)` at `PlayerSession.swift:32`.

## Evidence (observed)
| Id | Kind | Observation |
|---|---|---|
| E1 | stack_frame | IUO nil fatal error; first app frame `applyQuality` line 32 |
| E2 | stack_frame | Called from `QualitySheetViewModel.didDismiss()` during transition completion |
| E3 | source_code | `engine: PlaybackEngine!`; line 32 calls it without a nil check |
| E4 | source_code | `handleDidEnterBackground()` sets `engine = nil`; nothing recreates it on foreground |
| E5 | breadcrumb | sheet_opened → app_background → engine_released → app_foreground → sheet_dismissed; no `player_started` after foreground |
| E6 | custom_key | `engine_alive = false` |
| E7 | source_code | `didDismiss()` unconditionally calls `applyQuality` |
| E8 | thread_state | Main thread; no other thread active in app code |

## Hypotheses
1. **H1: Quality applied after background released the engine.**
   `ui_lifecycle`, **high**. The sheet outlives the engine; the unwrap is the
   symptom. Supported by E1–E7. Uncertain: not reproduced yet; `QualitySheet.swift`
   not inspected.
2. **H2: Concurrent release on a background queue.** `concurrency`, **low**.
   Against: notification is delivered on main, minutes pass between release and
   crash (E5), no other active thread (E8).

## Conclusion
**Probable root cause: H1.** Independent code, breadcrumb and custom-key
evidence agree. Not "confirmed" until reproduced.

## Missing information
- `QualitySheet.swift`, to confirm how `didDismiss()` is triggered.
- Whether a quality change should persist across background (product decision).

## Reproduction (likely)
Start playback → open quality sheet → Home → wait → return → dismiss sheet.

## Fix direction
If `engine` is nil, store the requested quality and apply it in
`start(stream:)`. Risk: quality takes effect on next start instead of
immediately; check other uses of `engine` after release.

## Verification
- Unit test: `applyQuality` after background does not crash; pending quality applied on next start.
- Simulator: reproduction steps before/after.
- Post-release: this issue's event count on the fixed version.

## Code change justified?
**Yes.** Strong, independent evidence; fix is local to one type.

No code was modified. If you want to proceed, run `/crash-fix player-quality-nil-engine`.
