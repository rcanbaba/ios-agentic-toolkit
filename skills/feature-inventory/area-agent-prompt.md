# Area agent prompt template

Used by the `feature-inventory` skill, step 2. Fill every `{{...}}`
placeholder; send one prompt per area, all agents in parallel.

---

You are inventorying one area of an existing iOS app so that it can be
rebuilt in a new app. Your output is read by other agents and by people who
have not seen this code. Be exact and complete; do not summarize.

Area: `{{AREA}}` ("{{TITLE}}")
Source root: `{{SOURCE_ROOT}}` (all paths below are relative to it)
Your paths: {{ASSIGNED_PATHS}}
Output file (the only file you may write): `{{MIGRATION_DIR}}/inventory/parts/{{AREA}}.json`

## Rules

1. Read-only. Do not modify, create or move any file in the repository other
   than your output file. No builds.
2. Read first: `{{MIGRATION_DIR}}/inventory/enumerations.json` (the exact
   identifiers that exist in the code) and the contract
   `{{PLUGIN_ROOT}}/schemas/feature-inventory-part.schema.json`.
3. Every `.swift` file under your paths must appear in some feature's
   `source_files` or in `unassigned_files` with a reason. Files outside your
   paths may be claimed when a feature clearly owns them; say so in
   `open_questions`.
4. Identifier fields (`api_methods`, `ws_incoming`, `ws_outgoing`,
   `push_types`, `app_routes`) take **exact names from enumerations.json, one
   per item**. Never invent a name, never write `"a, b"`, never describe in
   prose. If you cannot find the exact name, leave it out and note it in
   `open_questions`.
5. Granularity: one feature = one capability a user would recognize
   ("send a gift in a room", not "Room"). Sub-capabilities with their own UI
   or flow are separate features linked with `depends_on`. `depends_on` takes
   exact feature ids; for features in other areas use the id you expect and
   list it in `open_questions` as a guess.
6. Describe **current behavior only**, as the code implements it. No target
   behavior, no "should", no fixes. Observations about fragile or dead code go
   to `known_issues`, stated as observations.
7. `flow` is required for `core` and `high` features: ordered steps and state
   transitions, including what happens on failure and interruption. **Every
   step of a core/high flow carries `path/File.swift:line` evidence in the
   step text**, e.g. `"send: sendMessage, append on success
   (Features/Thread/ThreadViewModel.swift:29-43)"`. The validator checks that
   the file exists and the lines are inside it.
8. `user_actions` lists every action: primary buttons, secondary, long-press,
   swipe, context menu, sheet and alert actions, toggles.
9. `states_and_edge_cases`: loading, empty, error, permission denied, offline,
   backgrounding, interruption, limits, role changes, as implemented.
10. What you could not determine from code goes to `open_questions`, not into
    a feature.
11. `source_files` items are bare paths, one per item. A remark about a file
    ("shared with X", "mostly dead") goes to `source_file_notes`
    (`{"path": "note"}`), never into the path string.

## Process

- Walk your paths directory by directory. For each screen or manager, read
  the file, then its view model / coordinator, then the API and realtime
  calls it makes.
- Keep a running list of files you have claimed; at the end diff it against
  `ls -R` of your paths.
- Validate before you finish, and fix every error:
  `python3 {{PLUGIN_ROOT}}/scripts/validate_inventory_part.py {{MIGRATION_DIR}}/inventory/parts/{{AREA}}.json`

## Report back

Reply with: number of features by criticality, number of files claimed /
unassigned, the validator's last output line, and your `open_questions`
verbatim. Do not paste the JSON.
