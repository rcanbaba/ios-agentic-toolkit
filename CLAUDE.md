# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin** (not an iOS app): a general iOS toolkit made of
multiple workflows (crash, UI, release, ...). It is used from *other* iOS
repositories (`/plugin install` or `claude --plugin-dir <this repo>`). This
repo is where the toolkit is developed. Crash, design-system, app-migration and
app-port workflows are implemented; the "Planned" rows in the README workflow table are
intentionally unbuilt. `tools/` holds native helper apps (VNCBar) with thin
skills that trigger them; their docs go in `docs/tools/<tool>.md`.

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
- `skills/flow-spec/SKILL.md`: flow specs for critical flows, spec notes,
  the decision log and the independent audit (`audit-agent-prompt.md`).
- `skills/port-prep/SKILL.md`: core closure, untangling and the porting
  ledger; no scripts yet.
- `schemas/feature-inventory-part.schema.json` → `scripts/validate_inventory_part.py`
  (also used by `merge_inventory.py`); `schemas/inventory-verification.schema.json`
  → `scripts/apply_verification.py`; `schemas/flow-spec.schema.json` →
  `scripts/validate_flow_spec.py`. Deterministic pipeline:
  `extract_enumerations.py` (per-project config) → `merge_inventory.py` →
  `reconcile_inventory.py` → `apply_verification.py` → `render_inventory.py`;
  `render_flow_spec.py` and `render_pending.py` derive the Markdown.
  `scripts/evidence.py` resolves `file:line` references for all of them.
- Changing a schema or a script's behavior means updating its validator, the
  skill, the prompt template and `examples/migrations/pocket-threads`
  together, regenerating with `evals/feature-inventory/replay.sh --update`,
  and adding a case to `negative_cases.py` for every defect fixed.

## Port workflow: how the parts connect

- `skills/port-code/SKILL.md`: verbatim, build-error-driven port into the new
  app (writes there); consumes `port-prep`'s ledger and a path map.
  `scripts/port_missing_symbols.py` (missing symbol/member → unique legacy file;
  duplicates → temporary copies to remove) and `scripts/port_assets.py`
  (generated asset symbol → set; never AccentColor/app icons).
- `skills/ui-port/SKILL.md`: parallel restyle agents on the design system;
  `port-rules-template.md` and `restyle-agent-prompt.md` next to it;
  `scripts/find_legacy_styling.py` measures, batches and gates.
- Changing a port script's behavior means updating the skill, the fixture and
  `evals/app-port/expected/` (`evals/app-port/run.sh --update`), and adding a
  fixture case for every defect fixed.

## VNCBar tool: how the parts connect

- `tools/vnc-bar/`: Swift package for a macOS menu bar app; `build.sh`
  bundles, signs (stable identity by SHA-1) and installs it.
  `servers.json` holds servers; passwords only in the Keychain.
- `skills/remote-mac/SKILL.md`: reads `servers.json`, opens
  `vncbar://connect|type/<name>`; never handles passwords.
- Never put a password in the `vnc://` URL (Screen Sharing stores it in
  plaintext); never type unless the target window is verified and focused.
- Docs screenshots come from `VNCBar --render-screenshots` (synthetic
  servers); real hosts, users and window titles never enter the repo.

## Commands

```sh
# Validate an analysis against the contract (stdlib-only Python)
python3 scripts/validate_analysis.py examples/crashes/player-quality-nil-engine/analysis.json

# Design system: validate, generate (+ iOS typecheck), render, sample
python3 scripts/validate_design_system.py examples/design-systems/paper-lantern/design-system.json
python3 scripts/generate_swiftui.py examples/design-systems/paper-lantern/design-system.json --out examples/design-systems/paper-lantern/generated --check
scripts/render_specimen.sh examples/design-systems/paper-lantern/generated <out-dir>
swift scripts/sample_colors.swift <image.png>

# Migration: replay the whole pipeline on the example (must reproduce it exactly, twice)
evals/feature-inventory/replay.sh            # --update regenerates the example after an intended change
python3 evals/feature-inventory/negative_cases.py

# Port: replay the port scripts on the synthetic fixture
evals/app-port/run.sh                        # --update regenerates expected/

# VNCBar: unit tests, build + install, docs screenshots
(cd tools/vnc-bar && swift test)
tools/vnc-bar/build.sh --install
tools/vnc-bar/build/VNCBar.app/Contents/MacOS/VNCBar --render-screenshots docs/tools/images/vnc-bar

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
