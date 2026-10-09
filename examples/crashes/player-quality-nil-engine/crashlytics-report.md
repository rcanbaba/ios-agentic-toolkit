# Crashlytics issue (SYNTHETIC)

> Synthetic example input. App name, symbols, and numbers are invented.
> This is the shape of what you paste from the Crashlytics console.

**Issue:** PlayerSession.swift line 32 — PlayerSession.applyQuality(_:)
**Type:** Crash — `EXC_BREAKPOINT (SIGTRAP)`
**Message:** Fatal error: Unexpectedly found nil while implicitly unwrapping an Optional value
**Versions:** 3.4.0 (412), 3.4.1 (418) — first seen in 3.4.0
**Events / users (last 7 days):** 1,284 events / 911 users
**OS:** iOS 17.5 (38%), iOS 18.1 (51%), iOS 18.2 (11%)
**Devices:** iPhone 13, iPhone 14 Pro, iPhone 15, others
**Foreground/background:** 100% foreground

## Crashed thread: Thread 0 (com.apple.main-thread)

```
0  libswiftCore.dylib     _assertionFailure(_:_:file:line:flags:) + 244
1  SampleStream           PlayerSession.applyQuality(_:) (PlayerSession.swift:32)
2  SampleStream           QualitySheetViewModel.didDismiss() (QualitySheetViewModel.swift:20)
3  SampleStream           closure #2 in QualitySheet.body.getter (QualitySheet.swift:41)
4  SwiftUI                <redacted SwiftUI internals>
5  UIKitCore              -[UIViewController _setViewAppearState:isAnimating:] + 1032
6  UIKitCore              -[UIPresentationController transitionDidFinish:] + 520
7  UIKitCore              -[_UIViewControllerTransitionContext completeTransition:] + 116
8  UIKitCore              -[UIApplication _run] + 888
9  UIKitCore              UIApplicationMain + 340
10 SampleStream           main (SampleStreamApp.swift:12)
```

No other thread shows activity in SampleStream code.

## Custom keys

| Key | Value |
|---|---|
| engine_alive | false |
| player_screen | live |
| network_type | wifi |

## Logs / breadcrumbs (most recent last)

```
00:00.0  player_started
00:41.2  quality_sheet_opened
00:47.9  app_background
00:47.9  player_engine_released
03:12.5  app_foreground
03:15.0  quality_sheet_dismissed
```
