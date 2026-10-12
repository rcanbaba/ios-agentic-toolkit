# Missing-feature hunter prompt template

Used by the `feature-inventory` skill, step 5, once per inventory, in
parallel with the verifiers. Fill every `{{...}}` placeholder.

---

You are looking for features that an existing iOS app implements but its
feature inventory does not list. You do not verify existing features; other
agents do that. You sweep the code for capabilities and compare against the
inventory.

Source root: `{{SOURCE_ROOT}}`
Inventory: `{{MIGRATION_DIR}}/inventory/inventory.json`
Identifiers: `{{MIGRATION_DIR}}/inventory/enumerations.json`
Contract: `{{PLUGIN_ROOT}}/schemas/inventory-verification.schema.json`
Output file (the only file you may write): `{{MIGRATION_DIR}}/verification/missing-features.json` (scope `missing-features`)

## Sweep, exhaustively

Grep for each of these across the source root and check that every hit is
covered by some feature's `user_actions`, `entry_points` or identifier lists:

- every interaction site: `Button`, `onTapGesture`, `onLongPressGesture`,
  `contextMenu`, `swipeActions`, `Menu`, `.sheet`, `.alert`,
  `.confirmationDialog`, `Toggle`, `UIAction`, `addTarget`, gesture
  recognizers, `UIMenu`
- every case of the push type enum, the route and sub-route enums, the
  deeplink action enum, the tab enum
- every incoming realtime message handled anywhere (`case .<name>`)
- every settings / feature flag read (`featureFlags.`, `settings.`,
  `remoteConfig`, `UserDefaults` keys)
- every notification observer, background task, URL handler, universal link,
  share extension, widget or app-intent entry point
- every screen type (`View`, `UIViewController`) not claimed in any
  `source_files`

For each uncovered capability:

1. Read enough code to describe it as a feature: entry points, screens,
   actions, flow, states, identifiers, files.
2. Add a patch with `field: "new_feature"`, `action: "add"`, `value` a
   complete feature object per
   `{{PLUGIN_ROOT}}/schemas/feature-inventory-part.schema.json`, and a line
   in `missing_features` with evidence.
3. If the capability exists but is under-described (a feature lists the
   screen but not the action), use `add` patches on that feature instead of
   a new feature.

## Rules

- Read-only on the repository; write only your output file.
- Identifier fields take exact names from `enumerations.json`, one per item.
- Current behavior only; no judgments beyond `known_issues` observations.
- Every patch carries `path/File.swift:line` evidence.
- Self-check until valid:
  `python3 {{PLUGIN_ROOT}}/scripts/apply_verification.py --migration-dir {{MIGRATION_DIR}} --dry-run --scope missing-features`

## Report back

Reply with: what you swept (counts per category), the missing features found
with one line each, under-described features patched, and anything
ambiguous. "Nothing missing" is a valid result if the sweep was complete;
say what you checked.
