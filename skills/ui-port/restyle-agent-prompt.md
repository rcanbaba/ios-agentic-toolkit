# Restyle agent prompt template

Used by the `ui-port` skill, step 4. One agent per confirmed batch, all in
parallel. Fill every `{{...}}` placeholder. Keep the prompt short: the
project's port rules carry the shared instructions.

---

Read and follow `{{PORT_RULES}}` exactly.

Your folders (restyle only these; other agents own every other folder), under
`{{NEW_APP_SRC}}`: {{FOLDERS}}.
{{EXCLUSIONS}}

Find the work with:
`python3 {{PLUGIN_ROOT}}/scripts/find_legacy_styling.py {{STYLING_CONFIG}}`
(only the files under your folders are yours).

Visual direction for this batch: {{BATCH_DIRECTION}}
(name the reference preview, the surface type, and how the main elements of
these screens map to design-system components, for example "rows as
cards with round avatars, unread counts as accent badges").

Priority: {{PRIORITY}}
(a defect the user already reported in these folders, if any, with the
screen where it shows).

Do not run the project build. You may run `swiftc -parse` on files you
changed. When done, return the report the rules define.
