# iOS Crash Categories

Reference for the crash-analysis skill. Read the section for a category when it
becomes relevant. Categories are lenses, not boxes: a crash may fit none, or
several (e.g. a race that surfaces as a force unwrap).

Category keys match `hypotheses[].category` in the analysis schema.

## force_unwrap_or_precondition
- **Signatures:** `EXC_BREAKPOINT` / `SIGTRAP`; "Unexpectedly found nil while
  (implicitly) unwrapping an Optional value"; `Fatal error:` from
  `precondition`, `fatalError`, `try!`, `as!`, integer overflow.
- **Check:** where the value is set and cleared; whether an implicitly
  unwrapped property (`var x: T!`) can be nil at that call time.
- **Trap:** the unwrap is the symptom. Ask *why* it was nil. Often the real
  category is `ui_lifecycle`, `sdk_lifecycle` or `concurrency`.

## collection_bounds
- **Signatures:** "Index out of range"; `NSRangeException`; `EXC_BREAKPOINT`
  in `Array.subscript`.
- **Check:** where the index comes from (cached `IndexPath`, async-loaded
  data, stale selection); whether the collection mutates between count and
  access.
- **Trap:** a diffable/table update racing a data reload looks like a bounds
  bug but is `state_inconsistency` or `concurrency`.

## memory_lifetime
- **Signatures:** `EXC_BAD_ACCESS` (`KERN_INVALID_ADDRESS`), crash in
  `objc_msgSend`, `objc_release`, `swift_release`; zombie-like addresses.
- **Check:** `unowned` / `unowned(unsafe)` references, delegate properties
  declared `assign`/`unsafe_unretained` in ObjC, closures capturing objects
  that are torn down, C/SDK callbacks holding raw pointers to Swift objects.
- **Trap:** these are rarely reproducible on demand; look for deinit paths
  and callbacks that outlive their owner.

## concurrency
- **Signatures:** crashes in `swift_retain/release`, `Dictionary`/`Array`
  internals, `libdispatch`; same issue with many different top frames;
  Swift concurrency runtime traps.
- **Check:** shared mutable state accessed from multiple queues/actors;
  other threads in the report touching the same object; `@unchecked
  Sendable`; callbacks from SDKs on background queues.
- **Trap:** absence of a second thread in the report does not rule out a race.

## threading_requirement
- **Signatures:** "Main Thread Checker", `UIKit` assertions,
  "-[UIView ...] must be used from main thread only", CoreData context
  violations, `dispatch_assert_queue` failures.
- **Check:** completion handlers delivered on background queues touching UI
  or main-queue-bound state.

## ui_lifecycle
- **Signatures:** crashes after dismiss/pop, in `viewDidDisappear`,
  `deinit`, SwiftUI `onDisappear`/`task` cancellation, presenting on a
  view controller not in the hierarchy.
- **Check:** work that continues after the screen is gone (timers, observers,
  async tasks), strong/weak capture of view controllers.

## sdk_lifecycle
- **Signatures:** top frames inside a third-party SDK; breadcrumbs showing
  start/stop/background transitions before the crash.
- **Check:** whether the app calls the SDK after it was stopped/released or
  before it finished initialization; whether the SDK's documented threading
  and lifecycle requirements are respected.
- **Trap:** "the SDK crashed" is rarely the root cause; usually the app
  called it in an invalid state. Changing the SDK version is a last resort.

## state_inconsistency
- **Check:** two sources of truth drifting apart (cached vs live model, UI
  state vs data state), re-entrancy, events arriving in unexpected order.

## data_assumption
- **Check:** decoding of server/persisted data, unexpected empty/nil/format
  values, migrations, locale/time-zone-dependent parsing.

## objc_exception
- **Signatures:** `NSInvalidArgumentException`, `NSInternalInconsistencyException`,
  "unrecognized selector", KVO removal errors, `SIGABRT` after
  `objc_exception_throw`.
- **Check:** the exception reason string is usually the most precise
  evidence available; quote it verbatim.

## resource_pressure
- **Signatures:** watchdog terminations (`0x8badf00d`), jetsam / OOM (often
  not visible as normal crashes), `EXC_RESOURCE`.
- **Check:** main-thread blocking work at launch or scene transitions, large
  image/video buffers, unbounded caches.
- **Trap:** the stack shows where the app was when killed, not necessarily
  what consumed the time or memory.
