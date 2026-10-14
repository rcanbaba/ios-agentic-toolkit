# Audit agent prompt template

Used by the `flow-spec` skill, step 5. One fresh agent that wrote and verified
nothing in this migration. Fill every `{{...}}` placeholder.

---

You are auditing the migration artifacts of an existing iOS app before
anything is ported from them. Other agents and scripts produced them. Assume
they contain silent errors: data a script dropped, merged or attached
wrongly, and claims the code does not support. Check against the **code** and
against the scripts' own logs.

Source root: `{{SOURCE_ROOT}}`
Migration directory: `{{MIGRATION_DIR}}` (inventory/, verification/, flow-specs/, DECISIONS.md)
Output file (the only file you may write): `{{MIGRATION_DIR}}/AUDIT.md`

## Check

1. **What the scripts did to the parts.** Compare the parts as the area
   agents first wrote them (if kept) with `inventory/parts/`, and read
   `verification/applied.json` and `inventory/reconciliation.json`:
   - a list item lost, or a wrong claim left next to its correction
   - a replace that changed the wrong item; `skipped` or
     `annotate_unmatched` entries nobody resolved
   - a known issue annotated as false positive that is in fact real
   - an identifier attached to a feature that does not call it (open the
     call site); route names attached through UI tokens (`.main`, `.center`)
   - a merge that lost a summary or lowered criticality; a dropped id still
     referenced anywhere
   - notes moved out of `source_files` that were lost
2. **Claims against code.** Sample at least 10 core/high flow steps and 3
   transitions per spec; open each cited `file:line` and check that it shows
   what is claimed.
3. **Coverage leads.** In `inventory/coverage.json` → `text_coverage`, read
   the unreferenced names (unconsumed messages, API paths, SDKs, plist keys,
   notification names). Report any that point to a capability no feature
   describes.
4. **Specs and decisions.** Every core/high feature is in a spec or has a
   `spec_note` that holds up. Decided questions that align with an old app
   cite code that was read. No target behavior inside spec bodies.
5. **Decoding traps.** In screen and view-model files, look for extensions or
   conformances that change how core types decode or encode
   (`init(from decoder:)`, `encode(to:)`, `CodingKeys`, `: Decodable` on a
   model declared elsewhere). A port that misses them decodes differently
   without any error.

## Write AUDIT.md

One table, one row per finding, then a short summary of what you checked
(counts and samples), so a clean result is credible:

| # | Finding | Severity | Evidence | Resolution | Status |
|---|---|---|---|---|---|

- Severity: `data-loss` (a script or step lost or corrupted information),
  `wrong` (a claim the code contradicts), `incomplete` (something missing),
  `cosmetic`.
- Evidence: `path/File.swift:line` and/or the artifact path and key.
- Resolution: what would fix it (a patch, an override, a spec correction, a
  script change). Leave Status `open`; the orchestrator fills it in.

## Report back

Reply with: the number of findings by severity, the three most serious in
one line each, and what you sampled. Do not paste the table.
