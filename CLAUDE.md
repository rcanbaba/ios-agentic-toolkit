# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code **plugin** (not an iOS app): a general iOS toolkit made of
multiple workflows (crash, UI, release, ...). It is used from *other* iOS
repositories (`/plugin install` or `claude --plugin-dir <this repo>`). This
repo is where the toolkit is developed. Only the crash workflow is implemented;
the "Planned" rows in the README workflow table are intentionally unbuilt.

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

## Commands

```sh
# Validate an analysis against the contract (stdlib-only Python)
python3 scripts/validate_analysis.py examples/crashes/player-quality-nil-engine/analysis.json

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
