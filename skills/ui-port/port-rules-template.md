# Port rules template

Used by the `ui-port` skill, step 3. Copy into the project (for example
`Porting/UI_PORT_RULES.md`), fill every `{{...}}`, and delete lines that do
not apply. Every restyle agent reads this file; corrections go here, once.

---

# UI port rules ({{LEGACY_APP}} → {{NEW_APP}} design system)

You restyle screens that were copied verbatim from {{LEGACY_APP}} into
{{NEW_APP}}. **Do not build** (the integrator builds); only edit files.

## Paths

- New app sources: `{{NEW_APP_SRC}}`
- Legacy app (read-only reference): `{{LEGACY_SRC}}`
- Design system, read first: `{{DS_GUIDE}}`, `{{DS_TOKENS}}`, `{{DS_EXTRAS}}`
- Visual references: `{{DS_PREVIEWS}}`
- Approved reference screens to imitate: {{REFERENCE_FILES}}
- Shared components to reuse, never re-create: {{SHARED_COMPONENTS}}

## What to change

1. Only the styling and layout layer of views: fonts, colors, shapes,
   spacing, art. Keep every type name, initializer, property, binding,
   callback, view-model call, gesture, lifecycle hook, animation trigger,
   condition and localization key exactly as is. Never change logic, data
   flow, timers or network, realtime and SDK calls.
2. In non-view files (view models, models, managers) only replace legacy
   color, font or asset references with design-system tokens where they
   exist; touch nothing else.
3. Replace legacy styling with design-system equivalents:
   {{LEGACY_TO_DS_MAPPING}}
   (for example: `.font(.Brand.title)` → `.dsFont(.title)`;
   `Color("textPrimary")` → `DS.Colors.ink`; legacy icon art →
   SF Symbols or the design system's icon component).
4. Keep: remote images, server-provided media and animations, Lottie files
   that exist in the new app, third-party brand logos, and **product art**
   ({{KEPT_ART}}). Leave product art in place and list where it appears;
   it is redrawn later as one set.

## Surfaces

- Light screens: {{LIGHT_SURFACE_RULES}}
- Over media (video, camera, full-screen photos): {{STAGE_SURFACE_RULES}}
- Sheets and popups that open over media use the **light** sheet language.
  Before coloring text, check where the view is presented: a view reused in
  a light sheet must not keep text colored for a dark surface.

## Rules that real runs taught

- Apply shadows to the background shape only, never to a view that
  contains text or icons (the shadow duplicates the content), and add the
  outline stroke after the shadow (otherwise the outline is drawn twice).
- One primary action per screen. If the legacy screen had two, demote one
  to the secondary style and list it in your report.
- Dense rows (several numbers side by side, abbreviated values such as
  "149K", "2.7M") use a title or headline size, not the display/numeral
  size, with `minimumScaleFactor` and `monospacedDigit()`.
- Tap targets are at least 44pt; if growing one changes a row's height,
  say so in your report.
- Additive API changes only (a new optional parameter with a default), each
  listed in your report.
- Every rewritten view file gets one header comment:
  `// {{LEGACY_APP}} <relative path> — <what is kept>; design-system styling.`
- If a type you need is missing from the new app, do not create it; list it.

## Report

Files changed; anything not converted, with `file:line` and why; additive API
changes; every behavior or design choice you were unsure about, including
legacy behavior that looks wrong (do not fix it).
