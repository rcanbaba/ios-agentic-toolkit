# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin** (not an iOS app): a general iOS toolkit made of
multiple workflows (crash, UI, release, ...). It is used from *other* iOS
repositories (`/plugin install` or `claude --plugin-dir <this repo>`). This
repo is where the toolkit is developed. Crash, design-system and app-migration
workflows are implemented; the "Planned" rows in the README workflow table are
intentionally unbuilt.

README.md stays general (principles, building blocks, workflow catalog).
Workflow-specific design, usage, decisions and lessons go in
`docs/workflows/<workflow>.md`.

## Adding a workflow

1. Start from a real task the user has, and agree on the architecture first.
2. Follow the "Anatomy of a workflow" shape in the README; drop stages that
   don't apply rather than inventing new mechanisms.
3. Add `skills/<name>/`, plus a schema, validator, example and
   `evals/<name>/` only where they serve a current purpose.
4. Write `docs/workflows/<name>.md` and update the README workflow table.
5. After real runs, record generalizable lessons in that doc's
   "Lessons from real use" table.

## Crash workflow: how the parts connect

- `skills/crash-analysis/SKILL.md`: read-only investigation; writes
  `.crash-analysis/<issue-id>/analysis.{json,md}` in the *target* repo.
- `skills/crash-fix/SKILL.md`: `disable-model-invocation: true` (user-only
  `/crash-fix`); consumes `analysis.json`, requires plan approval, writes
  `verification.md`.
- `schemas/crash-analysis.schema.json`: the contract between the two skills.
  Changing it means updating `scripts/validate_analysis.py` (semantic rules),
  both skills, and the example `analysis.json` together.
- `rules/ios-engineering.md`: shared, domain-independent rules. Skills load
  it via `${CLAUDE_PLUGIN_ROOT}`; crash-specific knowledge belongs in the skill.

## Design-system workflow: how the parts connect

- `skills/design-system/SKILL.md`: agentic analysis, directions, human choice;
  works in `.design-system/<name>/` in the target repo.
- `schemas/design-system.schema.json` → `scripts/validate_design_system.py`
  (refs, Swift-safe names, WCAG contrast) → `scripts/generate_swiftui.py`
  (tokens + specimen; the generator re-runs validation and refuses invalid
  contracts) → `scripts/render_specimen.sh` (PNG renders on a simulator).
- `scripts/sample_colors.swift` measures colors from screenshots.
- Changing the schema means updating the validator, the generator, the
  skill and the `paper-lantern` example together, then regenerating.
- Both validators share `scripts/schema_lite.py`.

## Migration workflow: how the parts connect

- `skills/feature-inventory/SKILL.md`: orchestrates baseline extraction,
  parallel area agents, merge/coverage, reconciliation and independent
  verification; read-only on source, writes only `.migration/` in the
  target repo. Agent prompt templates live next to it.
- `skills/flow-spec/SKILL.md`: flow specs for critical flows and the
  decision log, consuming the inventory.
- `schemas/feature-inventory-part.schema.json` → `scripts/validate_inventory_part.py`
  (also used by `merge_inventory.py`); `schemas/inventory-verification.schema.json`
  → `scripts/apply_verification.py`; `schemas/flow-spec.schema.json` →
  `scripts/validate_flow_spec.py`. Deterministic pipeline:
  `extract_enumerations.py` (per-project config) → `merge_inventory.py` →
  `reconcile_inventory.py` → `apply_verification.py` → `render_inventory.py`;
  `render_flow_spec.py` derives the flow Markdown.
- Changing a schema means updating its validator, the skill, the prompt
  template and `examples/migrations/pocket-threads` together.

## Commands

```sh
# Validate an analysis against the contract (stdlib-only Python)
python3 scripts/validate_analysis.py examples/crashes/player-quality-nil-engine/analysis.json

# Design system: validate, generate (+ iOS typecheck), render, sample
python3 scripts/validate_design_system.py examples/design-systems/paper-lantern/design-system.json
python3 scripts/generate_swiftui.py examples/design-systems/paper-lantern/design-system.json --out examples/design-systems/paper-lantern/generated --check
scripts/render_specimen.sh examples/design-systems/paper-lantern/generated <out-dir>
swift scripts/sample_colors.swift <image.png>

# Migration: run the pipeline on the example (outputs are checked in; re-running reproduces them)
python3 scripts/extract_enumerations.py examples/migrations/pocket-threads/migration/enumerations.config.json --out examples/migrations/pocket-threads/migration/inventory/enumerations.json
python3 scripts/merge_inventory.py --migration-dir examples/migrations/pocket-threads/migration
python3 scripts/reconcile_inventory.py --migration-dir examples/migrations/pocket-threads/migration --overrides examples/migrations/pocket-threads/migration/reconcile.overrides.json
python3 scripts/apply_verification.py --migration-dir examples/migrations/pocket-threads/migration --dry-run
python3 scripts/render_inventory.py --migration-dir examples/migrations/pocket-threads/migration --title "Pocket Threads feature inventory"
python3 scripts/validate_flow_spec.py examples/migrations/pocket-threads/migration/flow-specs/send-message.json --migration-dir examples/migrations/pocket-threads/migration --require-decisions
python3 scripts/render_flow_spec.py examples/migrations/pocket-threads/migration/flow-specs/send-message.json

# Validate plugin/marketplace manifests and skill frontmatter
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
claude plugin validate skills

# Try the plugin inside a real iOS repo
cd <ios-repo> && claude --plugin-dir <path-to-this-repo>
```

## Rules for working on this repo

- **Git identity:** commits must be authored as `rcanbaba <rcanbabaoglu@gmail.com>`
  (set in repo-local git config). Check `git config user.email` before committing.
- **Public repo:** never add real crash reports, company code, production stack
  traces, user identifiers, Firebase configs or keys. Examples and eval
  fixtures must be synthetic; strip real data even if the user pastes it while
  iterating on a skill.
- **Grow from real use:** add a skill, script, schema field or subagent only
  when a real use case needs it, and explain why in the README's Design
  decisions. Do not scaffold roadmap items or create empty directories.
- **Deterministic first:** if a behavior can be specified reliably, make it a
  script or a validator rule rather than prose in a skill.
- Repo content is written in English.
