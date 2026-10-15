# Mobile UX rules for visual review

The rules a review finding may cite, by id. Each rule says what to look for in a
screenshot. They are deliberately few: a review reports what the user can see
and point at, not taste. Besides these ids, a finding may cite a contract
guideline (`DS-GUIDE`, quoting it) or a `check_ds_usage.py` rule
(`LINT:<rule>`).

The validator reads the ids from the table rows below; keep one rule per row.

## Type and density

| Id | Rule | Look for |
|---|---|---|
| `TYPE-ROW` | List rows, cells and stat rows use row-sized text (the contract's `row` styles, about 17pt and below); a display size belongs to the one hero element of a screen | A number or name in a repeated row that is as large as the screen title |
| `TYPE-HIERARCHY` | One clear title per screen; section titles distinct from body; at most three text sizes in one card | Competing large texts; a card where everything is bold |
| `TYPE-MIN` | No text below 11pt; secondary text still readable on its surface | Tiny captions, labels on badges that cannot be read at 1x |
| `TYPE-NUMBER` | Numbers keep their digits: monospaced in lists, abbreviated when long, never clipped | "12,48…", digits jumping between rows, a number cut by its container |

## Layout

| Id | Rule | Look for |
|---|---|---|
| `LAYOUT-OVERFLOW` | Nothing crosses the screen edge or the safe area unless it is a deliberate horizontal scroller | A row or card wider than the screen; content under the Dynamic Island or the home indicator |
| `LAYOUT-TRUNCATION` | Names truncate at the end with an ellipsis; numbers, prices and button labels never truncate | A cut button label, a wrapped price |
| `LAYOUT-ALIGNMENT` | Repeated elements share edges and baselines; side margins are the same across a screen | Avatars at different x positions; a list whose margins differ from the header's |
| `LAYOUT-SPACING` | Spacing follows the scale and groups related things; unrelated things are not closer than related ones | A label closer to the next row than to its own value |

## Touch

| Id | Rule | Look for |
|---|---|---|
| `TOUCH-TARGET` | Tap targets at least 44pt, with room between adjacent targets | Small icon buttons packed together; a close button at the screen corner edge |
| `TOUCH-PRIMARY` | At most one primary action per screen, visibly the primary one | Two equally loud buttons; the main action styled as secondary |

## Color and surface

| Id | Rule | Look for |
|---|---|---|
| `SURFACE-CONTRAST` | Text and icons are colored for the surface they sit on | Light text on a light sheet, text meant for a dark stage reused on a card |
| `SURFACE-PALETTE` | Colors come from the palette; content (photos, avatars, video) excepted | A legacy brand color, a system blue; `palette_check.py` clusters the palette cannot explain |
| `SURFACE-STATE` | Selected, disabled and pressed states are visibly different from the normal state | A selected tab that looks like the others; a disabled button that looks tappable |

## States and accessibility

| Id | Rule | Look for |
|---|---|---|
| `STATE-COVERAGE` | Loading, empty and error states exist and use the design system | A blank screen while loading; a raw error string |
| `A11Y-LARGE-TYPE` | At a large text size the layout reflows: no overlap, no clipped text, actions reachable | Overlapping labels, text cut at the bottom of a fixed-height card |
| `A11Y-DARK` | In dark appearance (when supported) every surface and text is legible and keeps the system's character | An unreadable element, a white card left on a dark screen |

## Design-system consistency

| Id | Rule | Look for |
|---|---|---|
| `DS-COMPONENT` | The same element is drawn the same way on every screen (shared components) | Three different badge shapes for the same level badge |
| `DS-SIGNATURE` | The contract's signature traits are present; the screen does not fall back to default iOS styling | Plain grouped lists, system blue buttons in a system that has neither |

## Severity

| Severity | Meaning |
|---|---|
| `blocker` | Content is unreadable or unusable: overflow that hides content, an action that cannot be reached, unreadable text |
| `major` | Visibly off the design system or the rules above, on a main screen or in many places |
| `minor` | Visible but small: one off-scale gap, one misaligned icon |
